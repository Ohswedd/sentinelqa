# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""GitHub issue lifecycle: dedup by fingerprint + close-on-next-pass (v1.5.0).

The base ``issue.py`` adapter is "create, or upsert by anchor". This
module sits on top and adds the two lifecycle behaviours teams ask
for:

* **Dedup by fingerprint** — two runs that surface the same logical
  issue produce a stable fingerprint (``module + category + code +
  title``). The lifecycle keys on the fingerprint instead of the
  per-run ``finding.id`` so a re-issued finding lands on the same
  issue.
* **Close on next pass** — when a previously open issue's
  fingerprint is no longer present in the most-recent findings, the
  lifecycle automatically closes the issue with a comment naming the
  resolving run.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from integrations._http import HttpClient, IntegrationHttpError
from integrations.github.issue import (
    DEFAULT_LABEL,
    GITHUB_API,
    GitHubIssueError,
    issue_anchor,
    render_issue_body,
    render_issue_title,
)

logger = logging.getLogger("sentinelqa.integrations.github.issue_lifecycle")

FINGERPRINT_ANCHOR_PREFIX: Final[str] = "[sentinelqa-fp:"
FINGERPRINT_ANCHOR_SUFFIX: Final[str] = "]"


@dataclass(frozen=True, slots=True)
class FindingFingerprint:
    """The stable identity of a finding across runs."""

    module: str
    category: str
    code: str
    title: str

    def digest(self) -> str:
        body = f"{self.module}|{self.category}|{self.code}|{self.title}"
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def fingerprint_anchor(fingerprint: FindingFingerprint) -> str:
    """Return the title anchor used to dedup issues across runs."""

    return f"{FINGERPRINT_ANCHOR_PREFIX}{fingerprint.digest()}{FINGERPRINT_ANCHOR_SUFFIX}"


def finding_fingerprint(finding: Any) -> FindingFingerprint:
    """Extract a :class:`FindingFingerprint` from any finding shape.

    Accepts both :class:`engine.domain.finding.Finding` objects and
    raw ``findings.json`` dicts so the lifecycle is callable on either
    side of the wire boundary.
    """

    module = str(getattr(finding, "module", "") or "")
    category = str(getattr(finding, "category", "") or "")
    title = str(getattr(finding, "title", "") or "")
    code = ""
    evidence = getattr(finding, "evidence", None)
    if isinstance(evidence, dict):
        for key in ("rule_id", "code", "check"):
            value = evidence.get(key)
            if isinstance(value, str) and value:
                code = value
                break
    if not code:
        cwe = getattr(finding, "cwe_id", None)
        if isinstance(cwe, str):
            code = cwe

    if not module:
        module = str(getattr(finding, "get", lambda *_a: "")("module")) or ""
    if not category:
        category = str(getattr(finding, "get", lambda *_a: "")("category")) or ""
    if not title:
        title = str(getattr(finding, "get", lambda *_a: "")("title")) or ""
    return FindingFingerprint(
        module=module,
        category=category,
        code=code,
        title=title,
    )


# --------------------------------------------------------------------------- #
# Per-finding template rendering
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class IssueTemplate:
    """Per-category template overrides for the issue body."""

    intro: str = ""
    extra_labels: tuple[str, ...] = field(default_factory=tuple)


# Curated templates that give the issue extra context per finding
# category. ``intro`` is prepended to the body; ``extra_labels`` are
# added alongside the default ``sentinelqa`` label.
_TEMPLATES: Final[dict[str, IssueTemplate]] = {
    "network-5xx": IssueTemplate(
        intro=(
            "**Severity (network):** This issue tracks a 5xx response observed "
            "during the audit. Inspect server logs and tie the response back to "
            "the request id in the evidence section.\n"
        ),
        extra_labels=("network", "5xx"),
    ),
    "page-error": IssueTemplate(
        intro=(
            "**Severity (browser):** A browser exception fired during the run. "
            "Add a window-level error handler around the listed source location.\n"
        ),
        extra_labels=("browser", "page-error"),
    ),
    "headers": IssueTemplate(
        intro=(
            "**Severity (headers):** A response-header policy issue. Apply the "
            "recommendation at the edge / reverse-proxy layer when possible.\n"
        ),
        extra_labels=("security", "headers"),
    ),
}


def render_lifecycle_body(finding: Any, fingerprint: FindingFingerprint) -> str:
    """Wrap the base ``render_issue_body`` output with the per-category intro."""

    template = _TEMPLATES.get(str(getattr(finding, "category", "")), IssueTemplate())
    base = render_issue_body(finding)
    fp_anchor = fingerprint_anchor(fingerprint)
    parts: list[str] = []
    if template.intro:
        parts.append(template.intro)
    parts.append(base)
    parts.append("")
    parts.append(
        f"_Lifecycle anchor: `{fp_anchor}` — this issue is closed automatically "
        "when the underlying finding is resolved._"
    )
    return "\n".join(parts)


def render_lifecycle_title(finding: Any, fingerprint: FindingFingerprint) -> str:
    """Inject the fingerprint anchor *and* the per-finding id anchor."""

    base = render_issue_title(finding)
    fp_anchor = fingerprint_anchor(fingerprint)
    if fp_anchor in base:
        return base
    if len(base) + len(fp_anchor) + 1 > 256:
        # Drop the per-finding id anchor — the fingerprint is the
        # lifecycle key, and the title cap is 256 chars.
        title_part = base.split("] ", 1)[-1]
        candidate = f"{fp_anchor} {title_part}"
        if len(candidate) <= 256:
            return candidate
        return candidate[:253] + "..."
    return f"{fp_anchor} {base}"


def labels_for(category: str, base_labels: Sequence[str] = (DEFAULT_LABEL,)) -> list[str]:
    extras = _TEMPLATES.get(category, IssueTemplate()).extra_labels
    seen: set[str] = set()
    out: list[str] = []
    for label in (*base_labels, *extras):
        if label not in seen:
            out.append(label)
            seen.add(label)
    return out


# --------------------------------------------------------------------------- #
# Lifecycle entry points
# --------------------------------------------------------------------------- #


def find_issue_by_fingerprint(
    *,
    repo: str,
    fingerprint: FindingFingerprint,
    client: HttpClient,
    state: str = "open",
) -> dict[str, Any] | None:
    """Search GitHub for an issue whose title carries the fingerprint anchor."""

    import urllib.parse

    anchor = fingerprint_anchor(fingerprint)
    query = f"repo:{repo} is:issue state:{state} {anchor} in:title"
    url = f"{GITHUB_API}/search/issues?q={urllib.parse.quote(query)}"
    try:
        response = client.get_json(url)
    except IntegrationHttpError as exc:
        raise GitHubIssueError(f"github issue search failed: {exc}") from exc
    if not isinstance(response, Mapping):
        return None
    for item in response.get("items") or []:
        if isinstance(item, Mapping) and anchor in (item.get("title") or ""):
            return dict(item)
    return None


def upsert_issue(
    *,
    repo: str,
    finding: Any,
    client: HttpClient,
    base_labels: Sequence[str] = (DEFAULT_LABEL,),
    auto_create: bool = False,
) -> dict[str, Any]:
    """Open or update the lifecycle issue tracking this finding's fingerprint."""

    if not auto_create:
        raise GitHubIssueError(
            "upsert_issue: auto-create is off. Pass auto_create=True " "to enable issue creation."
        )
    if not repo or "/" not in repo:
        raise GitHubIssueError(f"repo {repo!r} must be 'owner/name'.")

    fingerprint = finding_fingerprint(finding)
    existing = find_issue_by_fingerprint(repo=repo, fingerprint=fingerprint, client=client)
    title = render_lifecycle_title(finding, fingerprint)
    body = render_lifecycle_body(finding, fingerprint)
    labels = labels_for(str(getattr(finding, "category", "")), base_labels)

    if existing is not None:
        number = existing.get("number")
        url = f"{GITHUB_API}/repos/{repo}/issues/{number}"
        payload = {"title": title, "body": body, "labels": labels, "state": "open"}
        try:
            response = client.patch_json(url, payload)
        except IntegrationHttpError as exc:
            raise GitHubIssueError(f"github issue update failed: {exc}") from exc
        if not isinstance(response, Mapping):
            return existing
        return dict(response)

    url = f"{GITHUB_API}/repos/{repo}/issues"
    payload = {"title": title, "body": body, "labels": labels}
    try:
        response = client.post_json(url, payload)
    except IntegrationHttpError as exc:
        raise GitHubIssueError(f"github issue create failed: {exc}") from exc
    if not isinstance(response, Mapping):
        raise GitHubIssueError("github issue create response was not a JSON object")
    return dict(response)


def close_resolved_issues(
    *,
    repo: str,
    current_findings: Iterable[Any],
    client: HttpClient,
    run_id: str,
    base_labels: Sequence[str] = (DEFAULT_LABEL,),
) -> tuple[int, ...]:
    """Close every open lifecycle issue whose fingerprint is no longer present.

    Returns the list of issue numbers we closed so the caller can log
    them.
    """

    import urllib.parse

    label_query = "+".join(f'label:"{label}"' for label in base_labels)
    query = f"repo:{repo} is:issue is:open {label_query} {FINGERPRINT_ANCHOR_PREFIX} in:title"
    url = f"{GITHUB_API}/search/issues?q={urllib.parse.quote(query)}"
    try:
        response = client.get_json(url)
    except IntegrationHttpError as exc:
        raise GitHubIssueError(f"github issue search failed: {exc}") from exc

    current_digests: set[str] = {finding_fingerprint(f).digest() for f in current_findings}
    closed: list[int] = []
    items = response.get("items") if isinstance(response, Mapping) else []
    if not isinstance(items, list):
        items = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "")
        digest = _extract_digest(title)
        if not digest or digest in current_digests:
            continue
        number = item.get("number")
        if not isinstance(number, int):
            continue
        close_url = f"{GITHUB_API}/repos/{repo}/issues/{number}"
        try:
            client.patch_json(close_url, {"state": "closed"})
        except IntegrationHttpError as exc:
            logger.warning("could not close issue #%s: %s", number, exc)
            continue
        comment_url = f"{GITHUB_API}/repos/{repo}/issues/{number}/comments"
        try:
            client.post_json(
                comment_url,
                {"body": _resolution_comment(run_id)},
            )
        except IntegrationHttpError as exc:
            logger.warning(
                "closed issue #%s but could not post comment: %s",
                number,
                exc,
            )
        closed.append(number)
    return tuple(closed)


def _extract_digest(title: str) -> str:
    """Pull the ``sentinelqa-fp:...`` digest from a title."""

    start = title.find(FINGERPRINT_ANCHOR_PREFIX)
    if start == -1:
        return ""
    end = title.find(FINGERPRINT_ANCHOR_SUFFIX, start)
    if end == -1:
        return ""
    return title[start + len(FINGERPRINT_ANCHOR_PREFIX) : end]


def _resolution_comment(run_id: str) -> str:
    return f"_SentinelQA run `{run_id}` no longer reports this finding. " "Closing automatically."


# Backwards-compat re-export for the integrators who previously imported
# ``issue_anchor`` from here.
__all__ = [
    "FINGERPRINT_ANCHOR_PREFIX",
    "FINGERPRINT_ANCHOR_SUFFIX",
    "FindingFingerprint",
    "IssueTemplate",
    "close_resolved_issues",
    "find_issue_by_fingerprint",
    "fingerprint_anchor",
    "finding_fingerprint",
    "labels_for",
    "render_lifecycle_body",
    "render_lifecycle_title",
    "upsert_issue",
    "issue_anchor",
]
