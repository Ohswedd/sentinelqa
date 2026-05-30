"""Slack webhook poster (Phase 25.03)."""

from __future__ import annotations

from integrations.slack.poster import (
    SLACK_WEBHOOK_ENV,
    SlackPoster,
    SlackPosterError,
    SlackWebhookDeduper,
    post_payload,
)

__all__ = [
    "SlackPoster",
    "SlackPosterError",
    "SlackWebhookDeduper",
    "SLACK_WEBHOOK_ENV",
    "post_payload",
]
