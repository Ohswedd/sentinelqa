# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Microsoft Teams notifier (v1.5.0).

Posts a SentinelQA run summary as an Adaptive Card to an incoming
webhook URL (``https://<tenant>.webhook.office.com/...``).

Mirrors the :mod:`integrations.slack` shape: a stateless poster
class + a one-shot ``post_payload`` helper + a CLI entry point that
``sentinel report --notify teams`` dispatches into.
"""

from __future__ import annotations

from integrations.teams.poster import (
    TEAMS_WEBHOOK_ENV,
    TeamsPoster,
    TeamsPosterError,
    TeamsWebhookDeduper,
    post_payload,
    render_teams_payload,
)

__all__ = [
    "TEAMS_WEBHOOK_ENV",
    "TeamsPoster",
    "TeamsPosterError",
    "TeamsWebhookDeduper",
    "post_payload",
    "render_teams_payload",
]
