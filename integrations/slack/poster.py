"""Slack webhook poster reusing the Block Kit payload.

our engineering rules / §41:

- ``SLACK_WEBHOOK_URL`` is read at call time; never logged.
- The webhook URL is treated as a secret. The redacted URL we log
 strips the query string and the path segments after ``/services/``.
- We dedupe payloads within a 5-minute window so a retried CI job
 does not double-post; the dedup cache lives next to the run
 artifacts so it does not leak across users / hosts.

Two ways to invoke:

1. From Python — :class:`SlackPoster`.
2. As a script — ``python -m integrations.slack.poster --payload <file>``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from integrations._http import (
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
    redact_url,
)

SLACK_WEBHOOK_ENV: Final[str] = "SLACK_WEBHOOK_URL"
DEDUP_FILENAME: Final[str] = "slack-dedup.json"
DEFAULT_DEDUP_WINDOW_S: Final[int] = 300

logger = logging.getLogger("sentinelqa.integrations.slack")


class SlackPosterError(RuntimeError):
    """Raised when the poster cannot deliver the payload."""


# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------


@dataclass
class SlackWebhookDeduper:
    """JSON-on-disk dedup cache.

    The cache is a plain ``{key: timestamp}`` dict, pruned every read.
    ``key`` is ``sha256(payload-json + webhook-host)`` so two CI lanes
    posting different summaries to the same webhook are NOT deduped
    against each other, and the same summary posted to two webhooks
    is NOT deduped across them.
    """

    path: Path
    window_seconds: int = DEFAULT_DEDUP_WINDOW_S
    _now: Any = time.time

    def is_duplicate(self, *, payload: Mapping[str, Any], webhook_url: str) -> bool:
        key = self._key(payload=payload, webhook_url=webhook_url)
        store = self._load()
        cutoff = float(self._now()) - self.window_seconds
        store = {k: v for k, v in store.items() if v >= cutoff}
        self._save(store)
        return key in store

    def record(self, *, payload: Mapping[str, Any], webhook_url: str) -> None:
        key = self._key(payload=payload, webhook_url=webhook_url)
        store = self._load()
        cutoff = float(self._now()) - self.window_seconds
        store = {k: v for k, v in store.items() if v >= cutoff}
        store[key] = float(self._now())
        self._save(store)

    # --- internals --------------------------------------------------------

    def _key(self, *, payload: Mapping[str, Any], webhook_url: str) -> str:
        # Hash the full webhook URL so two CI lanes posting to different
        # incoming webhooks under the same host are NOT deduped against
        # each other. Hashing only the netloc collapses every Slack
        # webhook under ``hooks.slack.com``.
        digest = hashlib.sha256()
        digest.update(webhook_url.encode("utf-8"))
        digest.update(b"\n")
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        return digest.hexdigest()

    def _load(self) -> dict[str, float]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, Mapping):
            return {}
        return {str(k): float(v) for k, v in data.items() if isinstance(v, int | float)}

    def _save(self, store: Mapping[str, float]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(dict(store), sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            logger.warning("slack dedup: failed to persist cache: %s", exc)


# ---------------------------------------------------------------------------
# Poster
# ---------------------------------------------------------------------------


class SlackPoster:
    """Posts a Slack Block Kit payload to an incoming webhook URL."""

    def __init__(
        self,
        *,
        webhook_url: str,
        dedup: SlackWebhookDeduper | None = None,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not webhook_url.startswith("https://"):
            raise SlackPosterError("Slack webhook URL must be https://.")
        self._webhook_url = webhook_url
        self._dedup = dedup
        self._client = client or HttpClient(retry=retry)

    @property
    def webhook_url(self) -> str:
        return self._webhook_url

    def post(self, payload: Mapping[str, Any]) -> str:
        """Post ``payload`` (Block Kit JSON). Returns the Slack reply text."""

        if self._dedup is not None and self._dedup.is_duplicate(
            payload=payload, webhook_url=self._webhook_url
        ):
            logger.info(
                "slack: payload deduped (within %ss window)",
                self._dedup.window_seconds,
            )
            return "deduped"

        try:
            body = self._client.post_text(self._webhook_url, payload)
        except IntegrationHttpError as exc:
            raise SlackPosterError(
                f"slack post failed for {_redact_webhook(self._webhook_url)}: {exc}"
            ) from exc

        if self._dedup is not None:
            self._dedup.record(payload=payload, webhook_url=self._webhook_url)

        text = body.strip()
        if text.lower() != "ok":
            logger.warning(
                "slack: webhook %s replied %r (expected 'ok')",
                _redact_webhook(self._webhook_url),
                text[:200],
            )
        return text


def _redact_webhook(url: str) -> str:
    """Render a Slack webhook URL so the secret path is hidden.

    Slack's incoming-webhook URL embeds the secret in the path
    (``/services/T.../B.../X...``). ``integrations._http.redact_url``
    only strips the query string + userinfo; for Slack we additionally
    truncate everything after ``/services/`` so logs never carry the
    secret.
    """

    base = redact_url(url)
    marker = "/services/"
    idx = base.find(marker)
    if idx == -1:
        return base
    return base[: idx + len(marker)] + "<redacted>"


def post_payload(
    *,
    payload: Mapping[str, Any],
    webhook_url: str,
    dedup_path: Path | None = None,
    dedup_window_s: int = DEFAULT_DEDUP_WINDOW_S,
    client: HttpClient | None = None,
) -> str:
    """One-shot helper used by the CLI and by report --notify slack."""

    dedup = (
        SlackWebhookDeduper(path=dedup_path, window_seconds=dedup_window_s)
        if dedup_path is not None
        else None
    )
    return SlackPoster(webhook_url=webhook_url, dedup=dedup, client=client).post(payload)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="post_slack",
        description="Post a SentinelQA Block Kit summary to a Slack webhook.",
    )
    parser.add_argument(
        "--payload",
        required=True,
        type=Path,
        help="Path to a JSON file containing the Block Kit payload.",
    )
    parser.add_argument(
        "--webhook-env",
        default=SLACK_WEBHOOK_ENV,
        help=(
            "Environment variable holding the Slack webhook URL " f"(default: {SLACK_WEBHOOK_ENV})."
        ),
    )
    parser.add_argument(
        "--dedup-cache",
        type=Path,
        default=None,
        help="Optional path to a JSON dedup cache (5-min window).",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        webhook = os.environ.get(args.webhook_env, "").strip()
        if not webhook:
            raise SlackPosterError(
                f"webhook env var {args.webhook_env!r} is unset; refusing to call Slack."
            )
        if not args.payload.is_file():
            raise SlackPosterError(f"--payload not found: {args.payload}")
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise SlackPosterError(
                f"--payload {args.payload} must contain a JSON object (got "
                f"{type(payload).__name__})."
            )
        reply = post_payload(
            payload=payload,
            webhook_url=webhook,
            dedup_path=args.dedup_cache,
        )
        logger.info("slack: posted (%s)", reply or "ok")
        return 0
    except SlackPosterError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover - thin entry
    raise SystemExit(main())
