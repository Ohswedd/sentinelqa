"""GitHub commit-status poster (Phase 25, task 25.04).

Posts a single commit status with the SentinelQA quality score and
release decision. Designed to be called from CI (branch protection
can require the ``sentinelqa/quality-gate`` context) but is testable
purely via mocked HTTP.

CLAUDE.md §33: ``GITHUB_TOKEN`` is read from the environment only —
never logged, never echoed in error messages.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Iterable, Mapping
from typing import Any, Final, Literal

from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
)

GITHUB_API: Final[str] = "https://api.github.com"
DEFAULT_CONTEXT: Final[str] = "sentinelqa/quality-gate"
GitHubStatusState = Literal["pending", "success", "failure", "error"]
_VALID_STATES: Final[frozenset[str]] = frozenset({"pending", "success", "failure", "error"})

logger = logging.getLogger("sentinelqa.integrations.github.status")


class GitHubStatusError(RuntimeError):
    """Raised when the status cannot be posted."""


def post_commit_status(
    *,
    repo: str,
    sha: str,
    state: GitHubStatusState,
    description: str,
    target_url: str | None = None,
    context: str = DEFAULT_CONTEXT,
    client: HttpClient,
) -> dict[str, Any]:
    """POST a commit status. Returns the API response payload.

    ``description`` is clipped to 140 chars (GitHub's hard limit) so a
    long score breakdown never produces a 422 at runtime.
    """

    if state not in _VALID_STATES:
        raise GitHubStatusError(
            f"state {state!r} not valid; expected one of {sorted(_VALID_STATES)}."
        )
    if not repo or "/" not in repo:
        raise GitHubStatusError(f"repo {repo!r} must be 'owner/name'.")
    if not sha:
        raise GitHubStatusError("sha must be a non-empty commit SHA.")

    payload: dict[str, Any] = {
        "state": state,
        "description": description[:140],
        "context": context,
    }
    if target_url is not None:
        payload["target_url"] = target_url

    url = f"{GITHUB_API}/repos/{repo}/statuses/{sha}"
    try:
        response = client.post_json(url, payload)
    except IntegrationHttpError as exc:
        raise GitHubStatusError(f"github status post failed: {exc}") from exc
    if not isinstance(response, Mapping):
        raise GitHubStatusError("github status response was not a JSON object")
    return dict(response)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="post_github_status",
        description="Post a SentinelQA commit status to GitHub.",
    )
    parser.add_argument("--repo", required=True, help="`owner/repo` slug.")
    parser.add_argument("--sha", required=True, help="Commit SHA.")
    parser.add_argument(
        "--state",
        required=True,
        choices=sorted(_VALID_STATES),
        help="Commit status state.",
    )
    parser.add_argument("--description", required=True)
    parser.add_argument("--target-url", default=None)
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Env var holding the GitHub token (default: GITHUB_TOKEN).",
    )
    return parser


def _resolve_token(env_var: str) -> str:
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise GitHubStatusError(f"token env var {env_var!r} is empty; refusing to call GitHub.")
    return token


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        token = _resolve_token(args.token_env)
        client = HttpClient(
            auth=AuthHeader.bearer(token),
            retry=RetrySpec(),
            extra_headers={"X-GitHub-Api-Version": "2022-11-28"},
        )
        response = post_commit_status(
            repo=args.repo,
            sha=args.sha,
            state=args.state,
            description=args.description,
            target_url=args.target_url,
            context=args.context,
            client=client,
        )
        logger.info(
            "sentinelqa: posted %s commit status (%s) -> %s",
            args.state,
            args.context,
            response.get("url", "<no url>"),
        )
        return 0
    except GitHubStatusError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


__all__ = [
    "DEFAULT_CONTEXT",
    "GITHUB_API",
    "GitHubStatusError",
    "GitHubStatusState",
    "post_commit_status",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - thin entry
    raise SystemExit(main())
