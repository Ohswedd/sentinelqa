# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Microsoft Teams Adaptive-Card poster.

Teams accepts two webhook payload shapes — the legacy
``MessageCard`` and the newer ``Adaptive Card``. We ship Adaptive
Cards because they render correctly in both the Teams desktop and
mobile clients and Microsoft has deprecated MessageCards for
incoming webhooks (with a deprecation banner from June 2024).

The renderer takes the same shape as the Slack renderer takes
today: a structured :class:`TeamsRunSummary` of run metadata that
the CLI extracts from ``run.json`` / ``score.json``. The poster
itself is shape-agnostic and accepts an arbitrary JSON payload.
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

TEAMS_WEBHOOK_ENV: Final[str] = "SENTINELQA_TEAMS_WEBHOOK"
DEFAULT_DEDUP_WINDOW_S: Final[int] = 300

logger = logging.getLogger("sentinelqa.integrations.teams")


class TeamsPosterError(RuntimeError):
    """Raised when a Teams post cannot complete safely."""


# --------------------------------------------------------------------------- #
# Dedup
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TeamsWebhookDeduper:
    """A file-backed dedup cache for Teams webhook posts."""

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
        key = self._key(payload, webhook_url)
        record = self._load().get(key)
        if record is None:
            return False
        return (time.time() - float(record)) < self.window_seconds

    def record(self, *, payload: Mapping[str, Any], webhook_url: str) -> None:
        key = self._key(payload, webhook_url)
        state = self._load()
        state[key] = time.time()
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
class TeamsRunSummary:
    """The minimal run shape the renderer needs."""

    run_id: str
    status: str  # passed / failed / unsafe_blocked / incomplete / dry_run
    quality_score: float | None
    base_url: str
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    report_url: str | None = None


_STATUS_COLOR: Final[dict[str, str]] = {
    "passed": "Good",
    "failed": "Attention",
    "incomplete": "Warning",
    "unsafe_blocked": "Attention",
    "dry_run": "Accent",
}


def render_teams_payload(summary: TeamsRunSummary) -> dict[str, Any]:
    """Render an Adaptive Card payload for the Teams webhook."""

    color = _STATUS_COLOR.get(summary.status, "Default")
    facts: list[dict[str, str]] = [
        {"title": "Run", "value": summary.run_id},
        {"title": "Status", "value": summary.status.upper()},
    ]
    if summary.quality_score is not None:
        facts.append({"title": "Quality score", "value": f"{summary.quality_score:.1f}"})
    facts.append({"title": "Target", "value": summary.base_url})
    if summary.findings_by_severity:
        ladder = ", ".join(
            f"{severity}: {count}"
            for severity, count in sorted(summary.findings_by_severity.items())
            if count
        )
        if ladder:
            facts.append({"title": "Findings", "value": ladder})

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": f"SentinelQA — {summary.status.upper()}",
            "color": color,
        },
        {"type": "FactSet", "facts": facts},
    ]
    actions: list[dict[str, Any]] = []
    if summary.report_url:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "Open report",
                "url": summary.report_url,
            }
        )

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": body,
                    "actions": actions,
                },
            }
        ],
    }


# --------------------------------------------------------------------------- #
# Poster
# --------------------------------------------------------------------------- #


class TeamsPoster:
    """Posts an Adaptive Card payload to a Teams incoming webhook URL."""

    def __init__(
        self,
        *,
        webhook_url: str,
        dedup: TeamsWebhookDeduper | None = None,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not webhook_url.startswith("https://"):
            raise TeamsPosterError("Teams webhook URL must be https://.")
        self._webhook_url = webhook_url
        self._dedup = dedup
        self._client = client or HttpClient(retry=retry)

    @property
    def webhook_url(self) -> str:
        return self._webhook_url

    def post(self, payload: Mapping[str, Any]) -> str:
        """Post ``payload`` to the webhook. Returns the body verbatim."""

        if self._dedup is not None and self._dedup.is_duplicate(
            payload=payload, webhook_url=self._webhook_url
        ):
            logger.info(
                "teams: payload deduped (within %ss window)",
                self._dedup.window_seconds,
            )
            return "deduped"

        try:
            body = self._client.post_text(self._webhook_url, payload)
        except IntegrationHttpError as exc:
            raise TeamsPosterError(
                f"teams post failed for {_redact_webhook(self._webhook_url)}: {exc}"
            ) from exc

        if self._dedup is not None:
            self._dedup.record(payload=payload, webhook_url=self._webhook_url)

        return body.strip()


def _redact_webhook(url: str) -> str:
    """Render a Teams webhook URL without the secret path."""

    base = redact_url(url)
    # Teams URLs look like ``https://<tenant>.webhook.office.com/webhookb2/<id>@<tenant>/IncomingWebhook/<key>/<gid>``
    marker = "/webhookb2/"
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
    """One-shot helper used by the CLI and by ``report --notify teams``."""

    dedup = (
        TeamsWebhookDeduper(path=dedup_path, window_seconds=dedup_window_s)
        if dedup_path is not None
        else None
    )
    return TeamsPoster(webhook_url=webhook_url, dedup=dedup, client=client).post(payload)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinelqa-teams",
        description="Post a SentinelQA run summary as an Adaptive Card to Teams.",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get(TEAMS_WEBHOOK_ENV, ""),
        help=(f"Teams incoming-webhook URL " f"(or set {TEAMS_WEBHOOK_ENV} in the environment)."),
    )
    parser.add_argument(
        "--payload-file",
        type=Path,
        required=True,
        help="Path to a JSON file containing the Adaptive Card payload.",
    )
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
        sys.stderr.write(f"sentinelqa-teams: --webhook-url or {TEAMS_WEBHOOK_ENV} is required.\n")
        return 2
    try:
        payload = json.loads(ns.payload_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"sentinelqa-teams: cannot read payload: {exc}\n")
        return 2
    try:
        body = post_payload(
            payload=payload,
            webhook_url=ns.webhook_url,
            dedup_path=ns.dedup_cache,
            dedup_window_s=ns.dedup_window_s,
        )
    except TeamsPosterError as exc:
        sys.stderr.write(f"sentinelqa-teams: {exc}\n")
        return 1
    sys.stdout.write(body + "\n")
    return 0


__all__ = [
    "DEFAULT_DEDUP_WINDOW_S",
    "TEAMS_WEBHOOK_ENV",
    "TeamsPoster",
    "TeamsPosterError",
    "TeamsRunSummary",
    "TeamsWebhookDeduper",
    "main",
    "post_payload",
    "render_teams_payload",
]
