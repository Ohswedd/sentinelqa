"""Mocked tests for ``integrations.linear`` (Phase 25.06)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from engine.domain.finding import Finding, FindingLocation
from integrations._http import AuthHeader, HttpClient, IntegrationHttpError
from integrations.linear import (
    LINEAR_API_KEY_ENV,
    LinearConfigError,
    LinearIssueError,
    create_issue,
)
from integrations.linear.issue import LINEAR_GRAPHQL_URL, LinearCredentials


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__(auth=AuthHeader.header("Authorization", "k"))
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


def _finding(severity: str = "critical") -> Finding:
    return Finding(
        id="FND-PHASE2526001",
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.95,
        title="Session cookie missing HttpOnly",
        description="Login set-cookie lacked HttpOnly + Secure.",
        location=FindingLocation(route="/login"),
        evidence=(),
        recommendation="Set both flags.",
        affected_target="https://localhost:8080/login",
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


# Credentials ---------------------------------------------------------------


def test_credentials_from_env_reads_named_var() -> None:
    creds = LinearCredentials.from_env(environ={LINEAR_API_KEY_ENV: "k"})
    assert creds.api_key == "k"


def test_credentials_from_env_rejects_missing() -> None:
    with pytest.raises(LinearConfigError):
        LinearCredentials.from_env(environ={})


# create_issue --------------------------------------------------------------


def _creds() -> LinearCredentials:
    return LinearCredentials(api_key="key")


_OK_RESPONSE: dict[str, Any] = {
    "data": {
        "issueCreate": {
            "success": True,
            "issue": {
                "id": "abc",
                "identifier": "TEAM-42",
                "url": "https://linear.app/example/issue/TEAM-42",
            },
        }
    }
}


def test_create_issue_happy_path_returns_url() -> None:
    client = _FakeClient(responses=[_OK_RESPONSE])
    url = create_issue(
        credentials=_creds(),
        team_id="team-xyz",
        finding=_finding(),
        client=client,
    )
    assert url == "https://linear.app/example/issue/TEAM-42"
    method, request_url, body = client.calls[0]
    assert method == "POST"
    assert request_url == LINEAR_GRAPHQL_URL
    assert body is not None
    assert "mutation IssueCreate" in body["query"]
    input_ = body["variables"]["input"]
    assert input_["teamId"] == "team-xyz"
    assert input_["title"].startswith("[SentinelQA]")
    assert input_["priority"] == 1  # critical -> urgent


@pytest.mark.parametrize(
    "severity,expected_prio",
    [
        ("critical", 1),
        ("high", 2),
        ("medium", 3),
        ("low", 4),
        ("info", 0),
    ],
)
def test_priority_mapping(severity: str, expected_prio: int) -> None:
    client = _FakeClient(responses=[_OK_RESPONSE])
    create_issue(
        credentials=_creds(),
        team_id="team-xyz",
        finding=_finding(severity=severity),
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    assert body["variables"]["input"]["priority"] == expected_prio


def test_create_issue_rejects_empty_team_id() -> None:
    with pytest.raises(LinearConfigError):
        create_issue(
            credentials=_creds(),
            team_id="",
            finding=_finding(),
            client=_FakeClient(responses=[]),
        )


def test_create_issue_wraps_transport_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST -> HTTP 500: x")])
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_graphql_errors() -> None:
    client = _FakeClient(responses=[{"errors": [{"message": "kaboom"}]}])
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_missing_data_key() -> None:
    client = _FakeClient(responses=[{"misc": True}])
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_unsuccessful_response() -> None:
    client = _FakeClient(responses=[{"data": {"issueCreate": {"success": False, "issue": None}}}])
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_response_missing_url() -> None:
    client = _FakeClient(
        responses=[
            {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "x", "identifier": "T-1"},
                    }
                }
            }
        ]
    )
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_non_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    with pytest.raises(LinearIssueError):
        create_issue(
            credentials=_creds(),
            team_id="team-x",
            finding=_finding(),
            client=client,
        )


def test_description_redacts_credentials() -> None:
    finding = Finding(
        id="FND-PHASE2526002",
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity="high",
        confidence=0.9,
        title="t",
        description="leaked Authorization: Bearer abcdef0123456789ABCDEF",
        location=FindingLocation(),
        evidence=(),
        recommendation=None,
        suggested_fix=None,
        affected_target=None,
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    client = _FakeClient(responses=[_OK_RESPONSE])
    create_issue(
        credentials=_creds(),
        team_id="team-x",
        finding=finding,
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    desc = body["variables"]["input"]["description"]
    assert "abcdef0123456789ABCDEF" not in desc
