"""Mocked tests for ``integrations.github.issue`` (Phase 25.04)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from integrations._http import AuthHeader, HttpClient, IntegrationHttpError
from integrations.github.issue import (
    GitHubIssueError,
    create_issue_for_finding,
    find_existing_issue,
    issue_anchor,
    render_issue_body,
    render_issue_title,
)


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__(auth=AuthHeader.bearer("t"))
        self._responses = list(responses)
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None,
        parse_json: bool = True,
    ) -> Any:
        del parse_json
        self.calls.append((method, url, body))
        if not self._responses:
            raise AssertionError(f"unexpected {method} {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _finding(
    *,
    fid: str = "FND-PHASE2526001",
    severity: str = "critical",
    title: str = "Session cookie missing HttpOnly",
    description: str = "/login set-cookie lacked HttpOnly and Secure.",
    evidence: tuple[Evidence, ...] = (),
) -> Finding:
    return Finding(
        id=fid,
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
        title=title,
        description=description,
        location=FindingLocation(route="/login"),
        evidence=evidence,
        recommendation="Set HttpOnly + Secure on the session cookie.",
        affected_target="https://localhost:8080",
        suggested_fix="Add `httponly=True, secure=True` to session config.",
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Anchor + title
# ---------------------------------------------------------------------------


def test_issue_anchor_format() -> None:
    assert issue_anchor("FND-XYZ") == "[sentinelqa:FND-XYZ]"


def test_render_issue_title_includes_anchor() -> None:
    finding = _finding()
    title = render_issue_title(finding)
    assert title.startswith("[sentinelqa:FND-PHASE2526001]")
    assert "Session cookie missing HttpOnly" in title


def test_render_issue_title_clips_long_titles() -> None:
    # Finding.title is capped at 300 by Pydantic. Render must clip to 256.
    finding = _finding(title="x" * 300)
    title = render_issue_title(finding)
    assert len(title) <= 256


def test_render_issue_body_redacts_credentials() -> None:
    # Description with an Authorization-header-style literal must be
    # redacted before the body is built.
    finding = _finding(
        description="Login failed; Authorization: Bearer abcdef0123456789ABCDEF",
    )
    body = render_issue_body(finding)
    assert "abcdef0123456789ABCDEF" not in body
    # The redactor replaces secrets with REDACTED:..; the resulting
    # body must therefore not contain the raw secret literal.
    assert "REDACTED" in body.upper() or "Authorization" in body


def test_render_issue_body_lists_evidence_kinds(tmp_path: Path) -> None:
    ev = Evidence(id="EVD-PHASE2526001", type="screenshot", path=tmp_path / "shot.png")
    finding = _finding(evidence=(ev,))
    body = render_issue_body(finding)
    assert "screenshot" in body
    assert "shot.png" in body


def test_render_issue_body_omits_optional_sections() -> None:
    finding = Finding(
        id="FND-PHASE2526002",
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity="high",
        confidence=0.9,
        title="t",
        description="d",
        location=FindingLocation(),
        evidence=(),
        recommendation=None,
        suggested_fix=None,
        affected_target=None,
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    body = render_issue_body(finding)
    assert "## Recommendation" not in body
    assert "## Suggested fix" not in body
    assert "## Evidence" not in body
    assert "Affected target" not in body


# ---------------------------------------------------------------------------
# find_existing_issue
# ---------------------------------------------------------------------------


def test_find_existing_issue_returns_match() -> None:
    client = _FakeClient(
        responses=[
            {
                "items": [
                    {
                        "number": 7,
                        "title": "[sentinelqa:FND-PHASE2526001] foo",
                        "html_url": "https://github.com/o/r/issues/7",
                    }
                ]
            }
        ]
    )
    found = find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)
    assert found is not None
    assert found["number"] == 7
    method, url, _ = client.calls[0]
    assert method == "GET"
    assert "search/issues" in url
    assert "FND-PHASE2526001" in url


def test_find_existing_issue_returns_none_when_no_match() -> None:
    client = _FakeClient(responses=[{"items": []}])
    found = find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)
    assert found is None


def test_find_existing_issue_ignores_unanchored_match() -> None:
    client = _FakeClient(responses=[{"items": [{"number": 1, "title": "Not us"}]}])
    found = find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)
    assert found is None


def test_find_existing_issue_handles_non_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    found = find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)
    assert found is None


def test_find_existing_issue_handles_non_list_items() -> None:
    client = _FakeClient(responses=[{"items": "garbage"}])
    found = find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)
    assert found is None


def test_find_existing_issue_wraps_transport_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("GET -> HTTP 500")])
    with pytest.raises(GitHubIssueError):
        find_existing_issue(repo="o/r", finding_id="FND-PHASE2526001", client=client)


# ---------------------------------------------------------------------------
# create_issue_for_finding
# ---------------------------------------------------------------------------


def test_create_issue_refuses_without_auto_create_flag() -> None:
    client = _FakeClient(responses=[])
    with pytest.raises(GitHubIssueError) as exc:
        create_issue_for_finding(repo="o/r", finding=_finding(), client=client)
    assert "auto-create is off" in str(exc.value).lower()
    # No HTTP call when blocked.
    assert client.calls == []


def test_create_issue_rejects_bad_repo_slug() -> None:
    client = _FakeClient(responses=[])
    with pytest.raises(GitHubIssueError):
        create_issue_for_finding(
            repo="garbage", finding=_finding(), client=client, auto_create=True
        )


def test_create_issue_returns_existing_when_anchor_present() -> None:
    client = _FakeClient(
        responses=[
            {
                "items": [
                    {
                        "number": 7,
                        "title": "[sentinelqa:FND-PHASE2526001] dup",
                    }
                ]
            }
        ]
    )
    result = create_issue_for_finding(
        repo="o/r", finding=_finding(), client=client, auto_create=True
    )
    assert result["number"] == 7
    # Search performed; no POST.
    methods = [m for m, _, _ in client.calls]
    assert "POST" not in methods


def test_create_issue_posts_when_not_found() -> None:
    client = _FakeClient(
        responses=[
            {"items": []},  # search empty
            {
                "number": 11,
                "html_url": "https://github.com/o/r/issues/11",
                "title": "[sentinelqa:FND-PHASE2526001] x",
            },
        ]
    )
    result = create_issue_for_finding(
        repo="o/r", finding=_finding(), client=client, auto_create=True
    )
    assert result["number"] == 11
    methods = [m for m, _, _ in client.calls]
    assert methods == ["GET", "POST"]
    _, post_url, body = client.calls[1]
    assert post_url.endswith("/repos/o/r/issues")
    assert body is not None
    assert body["labels"] == ["sentinelqa"]
    assert body["title"].startswith("[sentinelqa:FND-PHASE2526001]")


def test_create_issue_wraps_post_failure() -> None:
    client = _FakeClient(
        responses=[
            {"items": []},
            IntegrationHttpError("POST -> HTTP 500"),
        ]
    )
    with pytest.raises(GitHubIssueError):
        create_issue_for_finding(repo="o/r", finding=_finding(), client=client, auto_create=True)


def test_create_issue_rejects_non_object_post_response() -> None:
    client = _FakeClient(
        responses=[
            {"items": []},
            ["not an object"],
        ]
    )
    with pytest.raises(GitHubIssueError):
        create_issue_for_finding(repo="o/r", finding=_finding(), client=client, auto_create=True)


def test_create_issue_supports_custom_labels() -> None:
    client = _FakeClient(responses=[{"items": []}, {"number": 1, "title": "x"}])
    create_issue_for_finding(
        repo="o/r",
        finding=_finding(),
        client=client,
        auto_create=True,
        labels=("sentinelqa", "security", "p0"),
    )
    body = client.calls[1][2]
    assert body is not None
    assert body["labels"] == ["sentinelqa", "security", "p0"]
