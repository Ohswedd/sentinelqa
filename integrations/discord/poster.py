# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Discord webhook poster.

Discord webhooks accept a simple ``{ "content": ..., "embeds": [...] }``
payload. We render the run summary as a single embed with a coloured
left-bar (red on failure, green on pass) and a fields ladder mirroring
the Slack / Teams notifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from integrations._http import (
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
    redact_url,
)

DISCORD_WEBHOOK_ENV: Final[str] = "SENTINELQA_DISCORD_WEBHOOK"
DEFAULT_DEDUP_WINDOW_S: Final[int] = 300

logger = logging.getLogger("sentinelqa.integrations.discord")


class DiscordPosterError(RuntimeError):
    """Raised when a Discord post cannot complete safely."""


# --------------------------------------------------------------------------- #
# Dedup
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiscordWebhookDeduper:
    """File-backed dedup cache, same shape as the Slack / Teams ones."""

    path: Path
    window_seconds: int = DEFAULT_DEDUP_WINDOW_S

    def _key(self, payload: Mapping[str, Any], webhook_url: str) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256()
        digest.update(webhook_url.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(body.encode("utf-8"))
        return digest.hexdigest()

    def is_duplicate(self, *, payload: Mapping[str, Any], webhook_url: str) -> bool:
        record = self._load().get(self._key(payload, webhook_url))
        if record is None:
            return False
        return (time.time() - float(record)) < self.window_seconds

    def record(self, *, payload: Mapping[str, Any], webhook_url: str) -> None:
        state = self._load()
        state[self._key(payload, webhook_url)] = time.time()
        self._save(state)

    def _load(self) -> dict[str, float]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return dict(data) if isinstance(data, dict) else {}

    def _save(self, state: dict[str, float]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Payload renderer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiscordRunSummary:
    """Same minimal shape as the Teams renderer."""

    run_id: str
    status: str
    quality_score: float | None
    base_url: str
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    report_url: str | None = None


# Discord embeds carry a 24-bit colour as an integer.
_STATUS_COLOUR: Final[dict[str, int]] = {
    "passed": 0x2ECC71,
    "failed": 0xE74C3C,
    "incomplete": 0xF1C40F,
    "unsafe_blocked": 0xE74C3C,
    "dry_run": 0x3498DB,
}


def render_discord_payload(summary: DiscordRunSummary) -> dict[str, Any]:
    """Render the Discord webhook payload."""

    colour = _STATUS_COLOUR.get(summary.status, 0x95A5A6)
    fields: list[dict[str, Any]] = [
        {"name": "Run", "value": summary.run_id, "inline": True},
        {"name": "Status", "value": summary.status.upper(), "inline": True},
    ]
    if summary.quality_score is not None:
        fields.append(
            {
                "name": "Quality score",
                "value": f"{summary.quality_score:.1f}",
                "inline": True,
            }
        )
    fields.append({"name": "Target", "value": summary.base_url})
    if summary.findings_by_severity:
        ladder = "\n".join(
            f"• {severity}: {count}"
            for severity, count in sorted(summary.findings_by_severity.items())
            if count
        )
        if ladder:
            fields.append({"name": "Findings", "value": ladder})
    embed: dict[str, Any] = {
        "title": f"SentinelQA — {summary.status.upper()}",
        "color": colour,
        "fields": fields,
    }
    if summary.report_url:
        embed["url"] = summary.report_url
    return {
        "username": "SentinelQA",
        "embeds": [embed],
    }


# --------------------------------------------------------------------------- #
# Poster
# --------------------------------------------------------------------------- #


class DiscordPoster:
    """Posts a payload to a Discord incoming-webhook URL."""

    def __init__(
        self,
        *,
        webhook_url: str,
        dedup: DiscordWebhookDeduper | None = None,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not webhook_url.startswith("https://"):
            raise DiscordPosterError("Discord webhook URL must be https://.")
        self._webhook_url = webhook_url
        self._dedup = dedup
        self._client = client or HttpClient(retry=retry)

    @property
    def webhook_url(self) -> str:
        return self._webhook_url

    def post(self, payload: Mapping[str, Any]) -> str:
        if self._dedup is not None and self._dedup.is_duplicate(
            payload=payload, webhook_url=self._webhook_url
        ):
            logger.info(
                "discord: payload deduped (within %ss window)",
                self._dedup.window_seconds,
            )
            return "deduped"
        try:
            body = self._client.post_text(self._webhook_url, payload)
        except IntegrationHttpError as exc:
            raise DiscordPosterError(
                f"discord post failed for {_redact_webhook(self._webhook_url)}: {exc}"
            ) from exc
        if self._dedup is not None:
            self._dedup.record(payload=payload, webhook_url=self._webhook_url)
        return body.strip()


def _redact_webhook(url: str) -> str:
    base = redact_url(url)
    marker = "/webhooks/"
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
    dedup = (
        DiscordWebhookDeduper(path=dedup_path, window_seconds=dedup_window_s)
        if dedup_path is not None
        else None
    )
    return DiscordPoster(webhook_url=webhook_url, dedup=dedup, client=client).post(payload)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinelqa-discord",
        description="Post a SentinelQA run summary to a Discord webhook.",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get(DISCORD_WEBHOOK_ENV, ""),
        help=f"Discord webhook URL (or set {DISCORD_WEBHOOK_ENV}).",
    )
    parser.add_argument("--payload-file", type=Path, required=True)
    parser.add_argument("--dedup-cache", type=Path, default=None)
    parser.add_argument(
        "--dedup-window-s",
        type=int,
        default=DEFAULT_DEDUP_WINDOW_S,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    ns = parser.parse_args(argv)
    if not ns.webhook_url:
        sys.stderr.write(
            f"sentinelqa-discord: --webhook-url or {DISCORD_WEBHOOK_ENV} is required.\n"
        )
        return 2
    try:
        payload = json.loads(ns.payload_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"sentinelqa-discord: cannot read payload: {exc}\n")
        return 2
    try:
        body = post_payload(
            payload=payload,
            webhook_url=ns.webhook_url,
            dedup_path=ns.dedup_cache,
            dedup_window_s=ns.dedup_window_s,
        )
    except DiscordPosterError as exc:
        sys.stderr.write(f"sentinelqa-discord: {exc}\n")
        return 1
    sys.stdout.write(body + "\n")
    return 0


__all__ = [
    "DEFAULT_DEDUP_WINDOW_S",
    "DISCORD_WEBHOOK_ENV",
    "DiscordPoster",
    "DiscordPosterError",
    "DiscordRunSummary",
    "DiscordWebhookDeduper",
    "main",
    "post_payload",
    "render_discord_payload",
]
