"""Credential-leak guard (Phase 25.07).

This test runs on every CI pass. It asserts that none of the Phase 25
integration credentials are present in the process environment. If any
of them are, real credentials have leaked into the test environment —
mocked tests would happily pass while exposing the secret to logs,
test output, and the GitHub Actions cache.

The list is intentionally exhaustive; add new env vars here whenever
a new integration ships.
"""

from __future__ import annotations

import os
from typing import Final

import pytest

# Each entry is the env var name carrying a Phase 25 integration secret.
# Membership of an empty string is fine — only non-empty values are a leak.
_FORBIDDEN_ENV_VARS: Final[frozenset[str]] = frozenset(
    {
        # BrowserStack
        "BROWSERSTACK_USERNAME",
        "BROWSERSTACK_ACCESS_KEY",
        # Sauce Labs
        "SAUCE_USERNAME",
        "SAUCE_ACCESS_KEY",
        # Slack
        "SLACK_WEBHOOK_URL",
        # GitHub (the deeper integration shares GITHUB_TOKEN with Phase 17;
        # we explicitly do NOT include it here because the CI run that posts
        # the PR comment uses GITHUB_TOKEN by design).
        # Jira
        "JIRA_USER_EMAIL",
        "JIRA_API_TOKEN",
        # Linear
        "LINEAR_API_KEY",
    }
)


def test_phase_25_credentials_not_present_in_environment() -> None:
    """Fail loudly if a Phase 25 secret leaked into CI."""

    leaked: list[str] = []
    for name in sorted(_FORBIDDEN_ENV_VARS):
        value = os.environ.get(name, "")
        if value.strip():
            leaked.append(name)

    if leaked:
        # Do NOT include the value in the failure message; the *name* is
        # enough to alert an operator that a real secret leaked. Listing
        # the value here would defeat the entire purpose of the guard.
        pytest.fail(
            "Phase 25 credential leak detected. The following env vars "
            "are non-empty in the test process: "
            f"{', '.join(leaked)}. "
            "CI MUST run with these unset (our engineering rules / Phase 25 task 25.07)."
        )


def test_forbidden_set_covers_all_integration_modules() -> None:
    """Sanity: the guard list keeps pace with the modules we ship."""

    expected_keys = {
        "BROWSERSTACK_USERNAME",
        "BROWSERSTACK_ACCESS_KEY",
        "SAUCE_USERNAME",
        "SAUCE_ACCESS_KEY",
        "SLACK_WEBHOOK_URL",
        "JIRA_USER_EMAIL",
        "JIRA_API_TOKEN",
        "LINEAR_API_KEY",
    }
    missing = expected_keys - _FORBIDDEN_ENV_VARS
    assert not missing, f"Phase 25 leak guard missing entries: {sorted(missing)}"
