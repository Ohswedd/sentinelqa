# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the v1.5.0 GitHub issue lifecycle layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from integrations._http import HttpClient
from integrations.github.issue_lifecycle import (
    FINGERPRINT_ANCHOR_PREFIX,
    FindingFingerprint,
    close_resolved_issues,
    finding_fingerprint,
    fingerprint_anchor,
    labels_for,
    render_lifecycle_body,
    render_lifecycle_title,
    upsert_issue,
)


@dataclass(frozen=True, slots=True)
class _StubEvidence:
    """Empty stand-in for the Evidence sequence on a finding."""


@dataclass(frozen=True, slots=True)
class _StubFinding:
    """Minimal Finding-shape stand-in (engine.domain.finding.Finding is too heavy here)."""

    id: str
    module: str
    category: str
    title: str
    severity: str = "high"
    description: str = "x"
    recommendation: str | None = None
    suggested_fix: str | None = None
    affected_target: str | None = None
    evidence: tuple = ()
    cwe_id: str | None = None


class _FakeGitHubClient(HttpClient):
    def __init__(
        self,
        *,
        get_responses: list[Any] | None = None,
        post_responses: list[Any] | None = None,
        patch_responses: list[Any] | None = None,
    ) -> None:
        super().__init__()
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, Mapping[str, Any]]] = []
        self.patch_calls: list[tuple[str, Mapping[str, Any]]] = []
        self._gets = list(get_responses or [])
        self._posts = list(post_responses or [])
        self._patches = list(patch_responses or [])

    def get_json(self, url: str) -> Any:
        self.get_calls.append(url)
        if not self._gets:
            raise AssertionError("no scripted GET response")
        return self._gets.pop(0)

    def post_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.post_calls.append((url, dict(payload)))
        if not self._posts:
            raise AssertionError("no scripted POST response")
        return self._posts.pop(0)

    def patch_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.patch_calls.append((url, dict(payload)))
        if not self._patches:
            raise AssertionError("no scripted PATCH response")
        return self._patches.pop(0)


def test_fingerprint_is_deterministic() -> None:
    fp1 = FindingFingerprint(module="security", category="headers", code="X", title="missing")
    fp2 = FindingFingerprint(module="security", category="headers", code="X", title="missing")
    assert fp1.digest() == fp2.digest()
    assert len(fp1.digest()) == 16


def test_fingerprint_changes_when_anchors_change() -> None:
    a = FindingFingerprint("security", "headers", "X", "missing").digest()
    b = FindingFingerprint("security", "headers", "Y", "missing").digest()
    assert a != b


def test_fingerprint_anchor_is_stable_string() -> None:
    fp = FindingFingerprint("security", "headers", "X", "missing")
    anchor = fingerprint_anchor(fp)
    assert anchor.startswith(FINGERPRINT_ANCHOR_PREFIX)
    assert anchor.endswith("]")


def test_finding_fingerprint_reads_evidence_code() -> None:
    finding = _StubFinding(
        id="FND-1",
        module="security",
        category="headers",
        title="CSP missing",
        evidence={"rule_id": "SEC-HEADERS-CSP-MISSING"},  # type: ignore[arg-type]
    )
    fp = finding_fingerprint(finding)
    assert fp.code == "SEC-HEADERS-CSP-MISSING"


def test_labels_for_includes_template_extras() -> None:
    labels = labels_for("headers")
    assert "sentinelqa" in labels
    assert "security" in labels
    assert "headers" in labels


def test_labels_for_unknown_category_returns_base_only() -> None:
    assert labels_for("nope") == ["sentinelqa"]


def test_render_lifecycle_title_injects_fingerprint_anchor() -> None:
    finding = _StubFinding(
        id="FND-XAAAAAAAAAAA",
        module="security",
        category="headers",
        title="CSP missing",
    )
    fp = finding_fingerprint(finding)
    title = render_lifecycle_title(finding, fp)
    assert fingerprint_anchor(fp) in title


def test_render_lifecycle_body_uses_template_intro() -> None:
    finding = _StubFinding(
        id="FND-X",
        module="api",
        category="network-5xx",
        title="5xx during checkout",
    )
    body = render_lifecycle_body(finding, finding_fingerprint(finding))
    assert "5xx response observed" in body
    assert "Lifecycle anchor" in body


def test_upsert_creates_when_no_match() -> None:
    client = _FakeGitHubClient(
        get_responses=[{"items": []}],
        post_responses=[{"number": 42}],
    )
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="CSP missing")
    result = upsert_issue(
        repo="owner/repo",
        finding=finding,
        client=client,
        auto_create=True,
    )
    assert result["number"] == 42
    assert client.post_calls
    url, payload = client.post_calls[0]
    assert "/issues" in url
    assert "sentinelqa-fp:" in payload["title"]
    assert payload["labels"]


def test_upsert_updates_when_match_found() -> None:
    fp = finding_fingerprint(
        _StubFinding(
            id="FND-X",
            module="security",
            category="headers",
            title="CSP missing",
        )
    )
    existing_title = f"{fingerprint_anchor(fp)} stale"
    client = _FakeGitHubClient(
        get_responses=[{"items": [{"number": 7, "title": existing_title}]}],
        patch_responses=[{"number": 7, "state": "open"}],
    )
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="CSP missing")
    result = upsert_issue(
        repo="owner/repo",
        finding=finding,
        client=client,
        auto_create=True,
    )
    assert result["number"] == 7
    assert client.patch_calls
    assert "/issues/7" in client.patch_calls[0][0]


def test_upsert_refuses_when_auto_create_off() -> None:
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="CSP missing")
    client = _FakeGitHubClient()
    from integrations.github.issue import GitHubIssueError

    with pytest.raises(GitHubIssueError):
        upsert_issue(
            repo="owner/repo",
            finding=finding,
            client=client,
            auto_create=False,
        )


def test_close_resolved_issues_closes_disappeared_fingerprints() -> None:
    """Issues whose fingerprint is no longer in the current run get closed."""

    fp_a = FindingFingerprint("security", "headers", "", "old")
    fp_b = FindingFingerprint("security", "headers", "", "still here")
    existing = [
        {"number": 1, "title": f"{fingerprint_anchor(fp_a)} stale title"},
        {"number": 2, "title": f"{fingerprint_anchor(fp_b)} still title"},
    ]
    client = _FakeGitHubClient(
        get_responses=[{"items": existing}],
        patch_responses=[{"state": "closed"}],
        post_responses=[{"id": 1}],  # comment post on the closed issue
    )
    # Only the "still here" finding remains in the current run. Its
    # fingerprint must match fp_b above so the close loop skips it.
    current = [
        _StubFinding(
            id="FND-B",
            module="security",
            category="headers",
            title="still here",
        )
    ]
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=current,
        client=client,
        run_id="RUN-XAAAAAAAAAAA",
    )
    assert closed == (1,)
    assert any("/issues/1" in url for url, _ in client.patch_calls)
    assert any("comments" in url for url, _ in client.post_calls)


def test_close_resolved_issues_skips_when_nothing_to_close() -> None:
    client = _FakeGitHubClient(get_responses=[{"items": []}])
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == ()
