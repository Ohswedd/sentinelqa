"""GitHub issue creator for SentinelQA findings (Phase 25, task 25.04).

Opens (or updates) an issue per ``critical`` finding when the calling
config / CLI explicitly opts in. **Off by default** —
``policy.github.auto_create_issue`` must be ``true`` AND the caller
must explicitly invoke this module.

Each finding tracked here uses a stable anchor in the issue title so
re-invocations upsert rather than spam the repo: ``[sentinelqa:FND-…]``.

our engineering rules / §41: token + finding evidence are redacted before
issue bodies hit the API. Real customer data, secrets, and full
stack traces never appear in issue bodies — the body shows the
recommendation + the redacted-evidence path summary only.
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any, Final

from engine.domain.finding import Finding
from engine.policy.redaction import redact

from integrations._http import HttpClient, IntegrationHttpError

GITHUB_API: Final[str] = "https://api.github.com"
ISSUE_ANCHOR_PREFIX: Final[str] = "[sentinelqa:"
ISSUE_ANCHOR_SUFFIX: Final[str] = "]"
DEFAULT_LABEL: Final[str] = "sentinelqa"

logger = logging.getLogger("sentinelqa.integrations.github.issue")


class GitHubIssueError(RuntimeError):
    """Raised when an issue cannot be created or upserted."""


def issue_anchor(finding_id: str) -> str:
    return f"{ISSUE_ANCHOR_PREFIX}{finding_id}{ISSUE_ANCHOR_SUFFIX}"


def render_issue_title(finding: Finding) -> str:
    raw_title = finding.title.replace("\n", " ").strip()
    anchor = issue_anchor(finding.id)
    base = f"{anchor} {raw_title}"
    if len(base) <= 256:
        return base
    # f"{anchor} {raw_title[:keep]} ..." = anchor + " " + keep + " ..."
    # = len(anchor) + 1 + keep + 4 ; we want total <= 256.
    keep = 256 - len(anchor) - 5
    return f"{anchor} {raw_title[:keep].rstrip()} ..."


def render_issue_body(finding: Finding) -> str:
    """Produce a redacted Markdown issue body."""

    lines: list[str] = []
    lines.append(f"**Severity:** {finding.severity}  ")
    lines.append(f"**Module:** {finding.module}  ")
    lines.append(f"**Category:** {finding.category}  ")
    if finding.affected_target:
        lines.append(f"**Affected target:** {redact(finding.affected_target)}  ")
    lines.append("")
    lines.append("## Description")
    lines.append(redact(finding.description))
    if finding.recommendation:
        lines.append("")
        lines.append("## Recommendation")
        lines.append(redact(finding.recommendation))
    if finding.suggested_fix:
        lines.append("")
        lines.append("## Suggested fix")
        lines.append(redact(finding.suggested_fix))
    if finding.evidence:
        lines.append("")
        lines.append("## Evidence")
        for ev in finding.evidence:
            lines.append(f"- {ev.type}: `{redact(str(ev.path))}`")
    lines.append("")
    lines.append(f"_Tracked by SentinelQA — anchor: `{issue_anchor(finding.id)}`._")
    return "\n".join(lines)


def find_existing_issue(
    *,
    repo: str,
    finding_id: str,
    client: HttpClient,
) -> dict[str, Any] | None:
    """Search for an open issue carrying the SentinelQA anchor."""

    anchor = issue_anchor(finding_id)
    query = f"repo:{repo} is:issue {anchor} in:title"
    url = f"{GITHUB_API}/search/issues?q={urllib.parse.quote(query)}"
    try:
        response = client.get_json(url)
    except IntegrationHttpError as exc:
        raise GitHubIssueError(f"github issue search failed: {exc}") from exc
    if not isinstance(response, Mapping):
        return None
    items = response.get("items") or []
    if not isinstance(items, Sequence):
        return None
    for item in items:
        if isinstance(item, Mapping) and anchor in (item.get("title") or ""):
            return dict(item)
    return None


def create_issue_for_finding(
    *,
    repo: str,
    finding: Finding,
    client: HttpClient,
    labels: Sequence[str] = (DEFAULT_LABEL,),
    auto_create: bool = False,
) -> dict[str, Any]:
    """Open (or return) a GitHub issue tracking ``finding``.

    ``auto_create`` MUST be True for any write to happen. The default
    is False so a misconfigured CI does not silently start opening
    issues against a target repo.
    """

    if not auto_create:
        raise GitHubIssueError(
            "create_issue_for_finding: auto-create is off. Pass "
            "auto_create=True (and set policy.github.auto_create_issue) "
            "to enable issue creation."
        )
    if not repo or "/" not in repo:
        raise GitHubIssueError(f"repo {repo!r} must be 'owner/name'.")

    existing = find_existing_issue(repo=repo, finding_id=finding.id, client=client)
    if existing is not None:
        logger.info(
            "github issue: existing issue #%s tracks finding %s; skipping create",
            existing.get("number"),
            finding.id,
        )
        return existing

    url = f"{GITHUB_API}/repos/{repo}/issues"
    payload: dict[str, Any] = {
        "title": render_issue_title(finding),
        "body": render_issue_body(finding),
        "labels": list(labels),
    }
    try:
        response = client.post_json(url, payload)
    except IntegrationHttpError as exc:
        raise GitHubIssueError(f"github issue create failed: {exc}") from exc
    if not isinstance(response, Mapping):
        raise GitHubIssueError("github issue create response was not a JSON object")
    return dict(response)


__all__ = [
    "DEFAULT_LABEL",
    "GITHUB_API",
    "GitHubIssueError",
    "ISSUE_ANCHOR_PREFIX",
    "ISSUE_ANCHOR_SUFFIX",
    "create_issue_for_finding",
    "find_existing_issue",
    "issue_anchor",
    "render_issue_body",
    "render_issue_title",
]
