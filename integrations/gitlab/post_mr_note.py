"""Upsert a SentinelQA merge-request note via the GitLab API (task 17.03).

Usage (invoked from `integrations/gitlab/.gitlab-ci.sentinel.yml`)::

    python integrations/gitlab/post_mr_note.py \\
        --report-markdown ./.sentinel/runs/<id>/report.md \\
        --api-url $CI_API_V4_URL \\
        --project-id $CI_PROJECT_ID \\
        --mr $CI_MERGE_REQUEST_IID

Looks for an existing note whose body begins with the
``<!-- sentinelqa:pr-comment -->`` anchor (the same anchor the GitHub
poster uses; the engine reporter emits it from
:mod:`engine.reporter.pr_comment`). If found, the note is edited in
place; otherwise a new note is created.

CLAUDE.md §33: the project access token is read from the environment
only — never logged, never echoed, never persisted.
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
USER_AGENT: Final[str] = "sentinelqa-mr-poster/1"
DEFAULT_RETRIES: Final[int] = 3
DEFAULT_BACKOFF_S: Final[float] = 1.0

logger = logging.getLogger("sentinelqa.mr_poster")


class PosterError(RuntimeError):
    """Raised when the poster cannot complete its job."""


@dataclass(frozen=True)
class _RetrySpec:
    max_attempts: int = DEFAULT_RETRIES
    base_backoff_s: float = DEFAULT_BACKOFF_S


class HttpClient:
    def __init__(self, *, token: str, retry: _RetrySpec | None = None) -> None:
        self._token = token
        self._retry = retry or _RetrySpec()

    def get_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return self._request("GET", url, body=None)

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", url, body=payload)
        assert isinstance(result, dict)
        return result

    def put_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request("PUT", url, body=payload)
        assert isinstance(result, dict)
        return result

    def _headers(self) -> dict[str, str]:
        return {
            "PRIVATE-TOKEN": self._token,
            "Accept": "application/json",
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
                if exc.code in {429, 500, 502, 503, 504} and attempt < self._retry.max_attempts:
                    sleep_for = self._retry.base_backoff_s * (2 ** (attempt - 1))
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    if retry_after:
                        with contextlib.suppress(ValueError):
                            sleep_for = max(sleep_for, float(retry_after))
                    logger.warning(
                        "gitlab poster: %s %s -> %d (attempt %d/%d), retrying in %.1fs",
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
                    f"GitLab API {method} returned HTTP {exc.code}: {_safe_reason(exc)}"
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < self._retry.max_attempts:
                    sleep_for = self._retry.base_backoff_s * (2 ** (attempt - 1))
                    logger.warning(
                        "gitlab poster: %s %s -> %s (attempt %d/%d), retrying in %.1fs",
                        method,
                        _redact_url(url),
                        exc.reason,
                        attempt,
                        self._retry.max_attempts,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise PosterError(f"GitLab API {method} failed: {exc.reason}") from exc

        raise PosterError(f"GitLab API {method} exhausted retries: {last_error!r}")


def _safe_reason(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return body[:200] or exc.reason or "unknown"


def _redact_url(url: str) -> str:
    sep_index = url.find("?")
    if sep_index == -1:
        return url
    return url[:sep_index] + "?<redacted>"


def upsert_note(
    *,
    api_url: str,
    project_id: str,
    mr_iid: int,
    body: str,
    client: HttpClient,
) -> dict[str, Any]:
    if not body.startswith(PR_COMMENT_ANCHOR):
        raise PosterError(
            "MR note body must begin with the SentinelQA anchor "
            f"({PR_COMMENT_ANCHOR!r}); refusing to post without it."
        )

    api_url = api_url.rstrip("/")
    existing = _find_existing_note(
        client=client, api_url=api_url, project_id=project_id, mr_iid=mr_iid
    )
    if existing is not None:
        url = f"{api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes/{existing['id']}"
        return client.put_json(url, {"body": body})

    url = f"{api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes"
    return client.post_json(url, {"body": body})


def _find_existing_note(
    *,
    client: HttpClient,
    api_url: str,
    project_id: str,
    mr_iid: int,
) -> dict[str, Any] | None:
    url = (
        f"{api_url}/projects/{project_id}/merge_requests/{mr_iid}/notes"
        "?per_page=100&sort=desc&order_by=updated_at"
    )
    payload = client.get_json(url)
    assert isinstance(payload, list)
    for note in payload:
        body = note.get("body") or ""
        if body.startswith(PR_COMMENT_ANCHOR):
            return note
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
        prog="post_mr_note",
        description="Upsert a SentinelQA summary into a GitLab merge-request note.",
    )
    parser.add_argument("--report-markdown", required=True, type=Path)
    parser.add_argument("--api-url", required=True, help="GitLab API base, e.g. CI_API_V4_URL.")
    parser.add_argument("--project-id", required=True, help="CI_PROJECT_ID value.")
    parser.add_argument("--mr", dest="mr_iid", required=True, type=int)
    parser.add_argument(
        "--token-env",
        default="SENTINELQA_GITLAB_TOKEN",
        help="Environment variable holding the GitLab token (default: SENTINELQA_GITLAB_TOKEN).",
    )
    return parser


def _resolve_token(env_var: str) -> str:
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise PosterError(
            f"token environment variable {env_var!r} is empty; refusing to call GitLab."
        )
    return token


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        body = _read_body(args.report_markdown)
        token = _resolve_token(args.token_env)
        client = HttpClient(token=token)
        result = upsert_note(
            api_url=args.api_url,
            project_id=args.project_id,
            mr_iid=args.mr_iid,
            body=body,
            client=client,
        )
        note_id = result.get("id")
        logger.info("SentinelQA MR note upserted (id=%s)", note_id or "unknown")
        return 0
    except PosterError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover - thin entry
    raise SystemExit(main())
