"""Jira issue adapter (, ).

``create_issue(finding) -> issue_url``. Off by default — the caller
passes ``project_key``; without it, the adapter raises. The Jira API
expects HTTP Basic auth (email + API token).

our engineering rules: credentials are read from the environment, never
logged. Finding evidence is redacted through ``engine.policy.redaction``
before being included in the description.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from engine.domain.finding import Finding
from engine.policy.redaction import redact

from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
)

JIRA_USER_ENV: Final[str] = "JIRA_USER_EMAIL"
JIRA_TOKEN_ENV: Final[str] = "JIRA_API_TOKEN"
_SEVERITY_TO_PRIORITY: Final[Mapping[str, str]] = {
    "critical": "Highest",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Lowest",
}


class JiraConfigError(ValueError):
    """Raised on missing credentials or invalid configuration."""


class JiraIssueError(RuntimeError):
    """Raised when an issue cannot be created."""


@dataclass(frozen=True)
class JiraCredentials:
    """Resolved Jira credentials. Never logged."""

    email: str
    api_token: str
    base_url: str

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str,
        email_env: str = JIRA_USER_ENV,
        token_env: str = JIRA_TOKEN_ENV,
        environ: Mapping[str, str] | None = None,
    ) -> JiraCredentials:
        env = environ if environ is not None else os.environ
        email = (env.get(email_env) or "").strip()
        token = (env.get(token_env) or "").strip()
        if not email or not token:
            raise JiraConfigError(
                f"Jira adapter requires both {email_env!r} and {token_env!r} to be set."
            )
        if not base_url.startswith("https://"):
            raise JiraConfigError(f"Jira base_url must be https:// (got {base_url!r}).")
        return cls(email=email, api_token=token, base_url=base_url.rstrip("/"))


def _render_description(finding: Finding) -> str:
    lines: list[str] = []
    lines.append(f"*Severity:* {finding.severity}")
    lines.append(f"*Module:* {finding.module}")
    lines.append(f"*Category:* {finding.category}")
    if finding.affected_target:
        lines.append(f"*Target:* {redact(finding.affected_target)}")
    lines.append("")
    lines.append(redact(finding.description))
    if finding.recommendation:
        lines.append("")
        lines.append("h2. Recommendation")
        lines.append(redact(finding.recommendation))
    lines.append("")
    lines.append(f"_SentinelQA finding {finding.id}_")
    return "\n".join(lines)


def create_issue(
    *,
    credentials: JiraCredentials,
    project_key: str,
    finding: Finding,
    issue_type: str = "Bug",
    client: HttpClient | None = None,
) -> str:
    """Create a Jira issue tracking ``finding`` and return its URL.

    The return value is the human-facing browse URL
    (``<base>/browse/<KEY>``); the raw REST self-link is logged for
    debugging only.
    """

    if not project_key:
        raise JiraConfigError("project_key must be a non-empty Jira project key.")

    http = client or HttpClient(
        auth=AuthHeader.basic(credentials.email, credentials.api_token),
        retry=RetrySpec(),
    )

    payload: dict[str, Any] = {
        "fields": {
            "project": {"key": project_key},
            "summary": f"[SentinelQA] {finding.title[:240]}",
            "issuetype": {"name": issue_type},
            "description": _render_description(finding),
            "priority": {"name": _SEVERITY_TO_PRIORITY.get(finding.severity, "Medium")},
            "labels": ["sentinelqa", finding.module],
        }
    }
    url = f"{credentials.base_url}/rest/api/3/issue"
    try:
        response = http.post_json(url, payload)
    except IntegrationHttpError as exc:
        raise JiraIssueError(f"jira issue create failed: {exc}") from exc
    if not isinstance(response, Mapping):
        raise JiraIssueError("jira issue create response was not a JSON object")
    key = response.get("key")
    if not isinstance(key, str) or not key:
        raise JiraIssueError("jira response did not contain an issue key")
    return f"{credentials.base_url}/browse/{key}"


__all__ = [
    "JIRA_TOKEN_ENV",
    "JIRA_USER_ENV",
    "JiraConfigError",
    "JiraCredentials",
    "JiraIssueError",
    "create_issue",
]
