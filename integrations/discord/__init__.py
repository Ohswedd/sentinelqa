# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Discord notifier (v1.5.0).

Posts a SentinelQA run summary as an embed card to a Discord
incoming-webhook URL
(``https://discord.com/api/webhooks/<id>/<token>``).
"""

from __future__ import annotations

from integrations.discord.poster import (
    DISCORD_WEBHOOK_ENV,
    DiscordPoster,
    DiscordPosterError,
    DiscordWebhookDeduper,
    post_payload,
    render_discord_payload,
)

__all__ = [
    "DISCORD_WEBHOOK_ENV",
    "DiscordPoster",
    "DiscordPosterError",
    "DiscordWebhookDeduper",
    "post_payload",
    "render_discord_payload",
]
