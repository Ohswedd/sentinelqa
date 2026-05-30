"""Linear issue adapter (Phase 25, task 25.06).

``create_issue(finding) -> issue_url``. Off by default — the caller
passes ``team_id``; without it the adapter raises. Linear uses
GraphQL with a header-based API key (``Authorization: <key>`` — no
``Bearer`` prefix).

CLAUDE.md §33: the API key is read from the environment only and
never logged. Finding evidence is redacted before it reaches Linear.
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

LINEAR_API_KEY_ENV: Final[str] = "LINEAR_API_KEY"
LINEAR_GRAPHQL_URL: Final[str] = "https://api.linear.app/graphql"

# 0 = no priority, 1 = urgent, 2 = high, 3 = medium, 4 = low.
_SEVERITY_TO_PRIORITY: Final[Mapping[str, int]] = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "info": 0,
}

_CREATE_ISSUE_MUTATION: Final[str] = (
    "mutation IssueCreate($input: IssueCreateInput!) {"
    "  issueCreate(input: $input) {"
    "    success"
    "    issue { id identifier url }"
    "  }"
    "}"
)


class LinearConfigError(ValueError):
    """Raised on missing credentials or invalid configuration."""


class LinearIssueError(RuntimeError):
    """Raised when an issue cannot be created."""


@dataclass(frozen=True)
class LinearCredentials:
    """Resolved Linear credentials. Never logged."""

    api_key: str

    @classmethod
    def from_env(
        cls,
        *,
        env_var: str = LINEAR_API_KEY_ENV,
        environ: Mapping[str, str] | None = None,
    ) -> LinearCredentials:
        env = environ if environ is not None else os.environ
        key = (env.get(env_var) or "").strip()
        if not key:
            raise LinearConfigError(f"Linear adapter requires {env_var!r} to be set.")
        return cls(api_key=key)


def _render_description(finding: Finding) -> str:
    lines: list[str] = []
    lines.append(f"**Severity:** {finding.severity}  ")
    lines.append(f"**Module:** {finding.module}  ")
    lines.append(f"**Category:** {finding.category}  ")
    if finding.affected_target:
        lines.append(f"**Target:** {redact(finding.affected_target)}  ")
    lines.append("")
    lines.append(redact(finding.description))
    if finding.recommendation:
        lines.append("")
        lines.append("## Recommendation")
        lines.append(redact(finding.recommendation))
    lines.append("")
    lines.append(f"_SentinelQA finding {finding.id}_")
    return "\n".join(lines)


def create_issue(
    *,
    credentials: LinearCredentials,
    team_id: str,
    finding: Finding,
    client: HttpClient | None = None,
) -> str:
    """Create a Linear issue tracking ``finding`` and return its URL."""

    if not team_id:
        raise LinearConfigError("team_id must be a non-empty Linear team ID.")

    http = client or HttpClient(
        auth=AuthHeader.header("Authorization", credentials.api_key),
        retry=RetrySpec(),
    )

    variables: dict[str, Any] = {
        "input": {
            "teamId": team_id,
            "title": f"[SentinelQA] {finding.title[:240]}",
            "description": _render_description(finding),
            "priority": _SEVERITY_TO_PRIORITY.get(finding.severity, 3),
            "labelIds": [],
        }
    }
    payload = {"query": _CREATE_ISSUE_MUTATION, "variables": variables}

    try:
        response = http.post_json(LINEAR_GRAPHQL_URL, payload)
    except IntegrationHttpError as exc:
        raise LinearIssueError(f"linear issue create failed: {exc}") from exc

    if not isinstance(response, Mapping):
        raise LinearIssueError("linear response was not a JSON object")
    if response.get("errors"):
        raise LinearIssueError(f"linear graphql errors: {response['errors']}")
    data = response.get("data")
    if not isinstance(data, Mapping):
        raise LinearIssueError("linear response was missing 'data'")
    create = data.get("issueCreate")
    if not isinstance(create, Mapping) or not create.get("success"):
        raise LinearIssueError("linear issueCreate did not succeed")
    issue = create.get("issue")
    if not isinstance(issue, Mapping):
        raise LinearIssueError("linear issueCreate response missing 'issue'")
    url = issue.get("url")
    if not isinstance(url, str) or not url:
        raise LinearIssueError("linear issue had no URL")
    return url


__all__ = [
    "LINEAR_API_KEY_ENV",
    "LINEAR_GRAPHQL_URL",
    "LinearConfigError",
    "LinearCredentials",
    "LinearIssueError",
    "create_issue",
]
