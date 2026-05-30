"""Upsert a SentinelQA PR comment via the GitHub REST API (task 17.03).

Usage (invoked from the composite Action — see
``integrations/github/workflows/sentinel-pr.yml``)::

    python integrations/github/post_pr_comment.py \\
        --report-markdown ./.sentinel/runs/<id>/report.md \\
        --repo owner/repo \\
        --pr 42

Reads the Markdown body from disk, locates an existing comment whose
body begins with the ``<!-- sentinelqa:pr-comment -->`` anchor (from
:mod:`engine.reporter.pr_comment`), and edits it in place when found;
otherwise creates a new comment.

CLAUDE.md §33: the ``GITHUB_TOKEN`` is read from the environment only —
it is never logged, never written to disk, never echoed back via the
process exit code, and never included in retry-error messages.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

PR_COMMENT_ANCHOR: Final[str] = "<!-- sentinelqa:pr-comment -->"
GITHUB_API: Final[str] = "https://api.github.com"
USER_AGENT: Final[str] = "sentinelqa-pr-poster/1"
DEFAULT_RETRIES: Final[int] = 3
DEFAULT_BACKOFF_S: Final[float] = 1.0

logger = logging.getLogger("sentinelqa.pr_poster")


class PosterError(RuntimeError):
    """Raised when the poster cannot complete its job."""


@dataclass(frozen=True)
class _RetrySpec:
    max_attempts: int = DEFAULT_RETRIES
    base_backoff_s: float = DEFAULT_BACKOFF_S


class HttpClient:
    """Tiny ``urllib``-based HTTP client.

    A class (rather than a free function) so tests can subclass and
    intercept calls without monkeypatching ``urllib.request`` globally.
    The intentional sparsity is by design — CLAUDE.md §35 frowns on
    pulling in ``requests`` just to upsert a comment.
    """

    def __init__(self, *, token: str, retry: _RetrySpec | None = None) -> None:
        self._token = token
        self._retry = retry or _RetrySpec()

    # --- public ----------------------------------------------------------------

    def get_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return self._request("GET", url, body=None)

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", url, body=payload)
        assert isinstance(result, dict)
        return result

    def patch_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("PATCH", url, body=payload)
        assert isinstance(result, dict)
        return result

    # --- internals -------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        encoded: bytes | None = None
        if body is not None:
            encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            request = urllib.request.Request(
                url=url,
                data=encoded,
                method=method,
                headers=self._headers(),
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read()
                    if not raw:
                        return {}
                    decoded = json.loads(raw.decode("utf-8"))
                    assert isinstance(decoded, list | dict)
                    return decoded
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in {429, 502, 503, 504} and attempt < self._retry.max_attempts:
                    sleep_for = self._retry.base_backoff_s * (2 ** (attempt - 1))
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    if retry_after:
                        with contextlib.suppress(ValueError):
                            sleep_for = max(sleep_for, float(retry_after))
                    logger.warning(
                        "github poster: %s %s -> %d (attempt %d/%d), retrying in %.1fs",
                        method,
                        _redact_url(url),
                        exc.code,
                        attempt,
                        self._retry.max_attempts,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise PosterError(
                    f"GitHub API {method} returned HTTP {exc.code}: {_safe_reason(exc)}"
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < self._retry.max_attempts:
                    sleep_for = self._retry.base_backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "github poster: %s %s -> %s (attempt %d/%d), retrying in %.1fs",
                        method,
                        _redact_url(url),
                        exc.reason,
                        attempt,
                        self._retry.max_attempts,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise PosterError(f"GitHub API {method} failed: {exc.reason}") from exc

        # All retries exhausted with non-HTTP errors.
        raise PosterError(f"GitHub API {method} exhausted retries: {last_error!r}")


def _safe_reason(exc: urllib.error.HTTPError) -> str:
    # GitHub bodies sometimes contain user content; clip to a small size
    # and never include header values (Authorization could echo back in
    # certain debug paths if we were careless).
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    body = body[:200]
    return body or exc.reason or "unknown"


def _redact_url(url: str) -> str:
    # We log URLs at warning level; strip any query string just in case
    # a caller pass-through embeds a token (defense in depth — current
    # call sites never do).
    sep_index = url.find("?")
    if sep_index == -1:
        return url
    return url[:sep_index] + "?<redacted>"


def upsert_comment(
    *,
    repo: str,
    pr_number: int,
    body: str,
    client: HttpClient,
) -> dict[str, Any]:
    """Find or create the SentinelQA PR comment and return the response payload."""

    if not body.startswith(PR_COMMENT_ANCHOR):
        raise PosterError(
            "PR comment body must begin with the SentinelQA anchor "
            f"({PR_COMMENT_ANCHOR!r}); refusing to post without it."
        )

    existing = _find_existing_comment(client=client, repo=repo, pr_number=pr_number)
    if existing is not None:
        url = f"{GITHUB_API}/repos/{repo}/issues/comments/{existing['id']}"
        return client.patch_json(url, {"body": body})

    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    return client.post_json(url, {"body": body})


def _find_existing_comment(
    *,
    client: HttpClient,
    repo: str,
    pr_number: int,
) -> dict[str, Any] | None:
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    payload = client.get_json(url)
    assert isinstance(payload, list)
    for comment in payload:
        body = comment.get("body") or ""
        if body.startswith(PR_COMMENT_ANCHOR):
            return comment
    return None


def _read_body(path: Path) -> str:
    if not path.is_file():
        raise PosterError(f"--report-markdown not found: {path}")
    body = path.read_text(encoding="utf-8")
    if not body.strip():
        raise PosterError(f"--report-markdown is empty: {path}")
    if not body.startswith(PR_COMMENT_ANCHOR):
        raise PosterError(f"--report-markdown does not begin with the SentinelQA anchor: {path}")
    return body


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="post_pr_comment",
        description="Upsert a SentinelQA summary into a GitHub PR comment.",
    )
    parser.add_argument("--report-markdown", required=True, type=Path)
    parser.add_argument("--repo", required=True, help="`owner/repo` slug.")
    parser.add_argument("--pr", required=True, type=int, help="PR number.")
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable holding the GitHub token (default: GITHUB_TOKEN).",
    )
    return parser


def _resolve_token(env_var: str) -> str:
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise PosterError(
            f"token environment variable {env_var!r} is empty; refusing to call GitHub."
        )
    return token


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        body = _read_body(args.report_markdown)
        token = _resolve_token(args.token_env)
        client = HttpClient(token=token)
        result = upsert_comment(
            repo=args.repo,
            pr_number=args.pr,
            body=body,
            client=client,
        )
        action = "edited" if "patch" in result.get("_method", "") else "posted"
        # GitHub returns a `html_url` we can log safely.
        url = result.get("html_url") or ""
        logger.info("SentinelQA PR comment %s (%s)", action, url or "unknown url")
        return 0
    except PosterError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover - thin entry
    raise SystemExit(main())
