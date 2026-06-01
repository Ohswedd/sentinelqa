"""GitLab commit-status setter (, ).

Posts a single commit status for a pipeline run. The MR note poster
 already handles inline summaries; this module sets the
external/pipeline status that GitLab branch protection / merge
checks watch.

our engineering rules: the project access token is read from the environment
only; never logged, never echoed in errors.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import urllib.parse
from collections.abc import Iterable, Mapping
from typing import Any, Final, Literal

from integrations._http import (
    AuthHeader,
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
)

DEFAULT_API_URL: Final[str] = "https://gitlab.com/api/v4"
DEFAULT_NAME: Final[str] = "sentinelqa/quality-gate"
GitLabStatusState = Literal["pending", "running", "success", "failed", "canceled"]
_VALID_STATES: Final[frozenset[str]] = frozenset(
    {"pending", "running", "success", "failed", "canceled"}
)

logger = logging.getLogger("sentinelqa.integrations.gitlab.status")


class GitLabStatusError(RuntimeError):
    """Raised when the status cannot be posted."""


def post_commit_status(
    *,
    api_url: str,
    project: str,
    sha: str,
    state: GitLabStatusState,
    description: str,
    target_url: str | None = None,
    name: str = DEFAULT_NAME,
    client: HttpClient,
) -> dict[str, Any]:
    """POST ``/projects/{id}/statuses/{sha}``.

    ``project`` can be a numeric ID or an URL-encoded path. The caller
    is responsible for URL-encoding namespaced paths
    (``group%2Frepo``).
    """

    if state not in _VALID_STATES:
        raise GitLabStatusError(
            f"state {state!r} not valid; expected one of {sorted(_VALID_STATES)}."
        )
    if not project:
        raise GitLabStatusError("project must be a non-empty ID or path.")
    if not sha:
        raise GitLabStatusError("sha must be a non-empty commit SHA.")

    api = api_url.rstrip("/")
    encoded_project = urllib.parse.quote(project, safe="")
    url = f"{api}/projects/{encoded_project}/statuses/{sha}"

    payload: dict[str, Any] = {
        "state": state,
        "description": description[:255],
        "name": name,
    }
    if target_url is not None:
        payload["target_url"] = target_url

    try:
        response = client.post_json(url, payload)
    except IntegrationHttpError as exc:
        raise GitLabStatusError(f"gitlab status post failed: {exc}") from exc
    if not isinstance(response, Mapping):
        raise GitLabStatusError("gitlab status response was not a JSON object")
    return dict(response)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="post_gitlab_status",
        description="Post a SentinelQA pipeline commit status to GitLab.",
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--project", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument(
        "--state",
        required=True,
        choices=sorted(_VALID_STATES),
    )
    parser.add_argument("--description", required=True)
    parser.add_argument("--target-url", default=None)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument(
        "--token-env",
        default="GITLAB_TOKEN",
        help="Env var holding the GitLab token (default: GITLAB_TOKEN).",
    )
    return parser


def _resolve_token(env_var: str) -> str:
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise GitLabStatusError(f"token env var {env_var!r} is empty; refusing to call GitLab.")
    return token


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        token = _resolve_token(args.token_env)
        client = HttpClient(
            auth=AuthHeader.header("PRIVATE-TOKEN", token),
            retry=RetrySpec(),
        )
        response = post_commit_status(
            api_url=args.api_url,
            project=args.project,
            sha=args.sha,
            state=args.state,
            description=args.description,
            target_url=args.target_url,
            name=args.name,
            client=client,
        )
        logger.info(
            "sentinelqa: posted %s pipeline status (%s) -> %s",
            args.state,
            args.name,
            response.get("ref", "<no ref>"),
        )
        return 0
    except GitLabStatusError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


__all__ = [
    "DEFAULT_API_URL",
    "DEFAULT_NAME",
    "GitLabStatusError",
    "GitLabStatusState",
    "post_commit_status",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - thin entry
    raise SystemExit(main())
