"""Mocked tests for ``integrations.jira``."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from engine.domain.finding import Finding, FindingLocation
from integrations._http import AuthHeader, HttpClient, IntegrationHttpError
from integrations.jira import (
    JIRA_TOKEN_ENV,
    JIRA_USER_ENV,
    JiraConfigError,
    JiraIssueError,
    create_issue,
)
from integrations.jira.issue import JiraCredentials


class _FakeClient(HttpClient):
    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__(auth=AuthHeader.basic("u", "k"))
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
        description="Login endpoint set-cookie lacked HttpOnly + Secure.",
        location=FindingLocation(route="/login"),
        evidence=(),
        recommendation="Add HttpOnly + Secure to the session cookie.",
        affected_target="https://localhost:8080/login",
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


# Credentials ---------------------------------------------------------------


def test_credentials_from_env_reads_named_vars() -> None:
    creds = JiraCredentials.from_env(
        base_url="https://example.atlassian.net",
        environ={JIRA_USER_ENV: "me@example.com", JIRA_TOKEN_ENV: "tok"},
    )
    assert creds.email == "me@example.com"
    assert creds.api_token == "tok"
    assert creds.base_url == "https://example.atlassian.net"


def test_credentials_from_env_rejects_missing() -> None:
    with pytest.raises(JiraConfigError):
        JiraCredentials.from_env(base_url="https://x.atlassian.net", environ={})


def test_credentials_from_env_rejects_http() -> None:
    with pytest.raises(JiraConfigError):
        JiraCredentials.from_env(
            base_url="http://insecure.example.com",
            environ={JIRA_USER_ENV: "a", JIRA_TOKEN_ENV: "b"},
        )


def test_credentials_strip_trailing_slash() -> None:
    creds = JiraCredentials.from_env(
        base_url="https://x.atlassian.net/",
        environ={JIRA_USER_ENV: "a", JIRA_TOKEN_ENV: "b"},
    )
    assert creds.base_url == "https://x.atlassian.net"


# create_issue --------------------------------------------------------------


def _creds() -> JiraCredentials:
    return JiraCredentials(
        email="me@example.com",
        api_token="tok",
        base_url="https://x.atlassian.net",
    )


def test_create_issue_happy_path_returns_browse_url() -> None:
    client = _FakeClient(responses=[{"id": "10001", "key": "SEC-42"}])
    url = create_issue(
        credentials=_creds(),
        project_key="SEC",
        finding=_finding(),
        client=client,
    )
    assert url == "https://x.atlassian.net/browse/SEC-42"
    method, request_url, body = client.calls[0]
    assert method == "POST"
    assert request_url == "https://x.atlassian.net/rest/api/3/issue"
    assert body is not None
    fields = body["fields"]
    assert fields["project"]["key"] == "SEC"
    assert fields["summary"].startswith("[SentinelQA]")
    assert fields["priority"]["name"] == "Highest"
    assert "sentinelqa" in fields["labels"]
    assert "security" in fields["labels"]


def test_create_issue_priority_mapping_for_medium() -> None:
    client = _FakeClient(responses=[{"key": "SEC-1"}])
    create_issue(
        credentials=_creds(),
        project_key="SEC",
        finding=_finding(severity="medium"),
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    assert body["fields"]["priority"]["name"] == "Medium"


def test_create_issue_rejects_empty_project_key() -> None:
    with pytest.raises(JiraConfigError):
        create_issue(
            credentials=_creds(),
            project_key="",
            finding=_finding(),
            client=_FakeClient(responses=[]),
        )


def test_create_issue_wraps_transport_error() -> None:
    client = _FakeClient(responses=[IntegrationHttpError("POST -> HTTP 500: x")])
    with pytest.raises(JiraIssueError):
        create_issue(
            credentials=_creds(),
            project_key="SEC",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_non_object_response() -> None:
    client = _FakeClient(responses=[["unexpected"]])
    with pytest.raises(JiraIssueError):
        create_issue(
            credentials=_creds(),
            project_key="SEC",
            finding=_finding(),
            client=client,
        )


def test_create_issue_rejects_missing_key() -> None:
    client = _FakeClient(responses=[{"id": "10001"}])
    with pytest.raises(JiraIssueError):
        create_issue(
            credentials=_creds(),
            project_key="SEC",
            finding=_finding(),
            client=client,
        )


def test_create_issue_redacts_credentials_in_description() -> None:
    finding = Finding(
        id="FND-PHASE2526002",
        run_id="RUN-LINTAAAAAAAA",
        module="security",
        category="security/cookies",
        severity="high",
        confidence=0.9,
        title="t",
        description="Authorization: Bearer abcdef0123456789ABCDEF leaked",
        location=FindingLocation(),
        evidence=(),
        recommendation=None,
        suggested_fix=None,
        affected_target=None,
        created_at=datetime(2026, 5, 30, tzinfo=UTC),
    )
    client = _FakeClient(responses=[{"key": "SEC-1"}])
    create_issue(
        credentials=_creds(),
        project_key="SEC",
        finding=finding,
        client=client,
    )
    body = client.calls[0][2]
    assert body is not None
    assert "abcdef0123456789ABCDEF" not in body["fields"]["description"]
