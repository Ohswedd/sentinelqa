# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Mocked tests for the three v1.5.0 notifiers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from integrations._http import HttpClient
from integrations.discord import (
    DiscordPoster,
    DiscordPosterError,
    DiscordWebhookDeduper,
    render_discord_payload,
)
from integrations.discord.poster import DiscordRunSummary
from integrations.pagerduty import (
    PagerDutyTrigger,
    PagerDutyTriggerRequest,
    should_trigger,
)
from integrations.pagerduty.trigger import (
    build_resolve_payload,
    build_trigger_payload,
)
from integrations.teams import (
    TeamsPoster,
    TeamsPosterError,
    TeamsWebhookDeduper,
    render_teams_payload,
)
from integrations.teams.poster import TeamsRunSummary


class _FakeClient(HttpClient):
    """Same shape as the Slack test seam — captures calls + replays scripted responses."""

    def __init__(self, *, responses: list[Any]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def post_text(self, url: str, payload: Mapping[str, Any]) -> str:
        self.calls.append((url, dict(payload)))
        if not self._responses:
            raise AssertionError("no scripted response")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return str(nxt)


# --------------------------------------------------------------------------- #
# Microsoft Teams
# --------------------------------------------------------------------------- #


def test_teams_constructor_rejects_http_webhook() -> None:
    with pytest.raises(TeamsPosterError):
        TeamsPoster(webhook_url="http://tenant.webhook.office.com/x")


def test_teams_post_happy_path() -> None:
    client = _FakeClient(responses=["1"])
    poster = TeamsPoster(
        webhook_url="https://tenant.webhook.office.com/webhookb2/a/b",
        client=client,
    )
    result = poster.post({"type": "message"})
    assert result == "1"
    url, payload = client.calls[0]
    assert "webhookb2" in url
    assert payload == {"type": "message"}


def test_teams_render_passed_summary() -> None:
    summary = TeamsRunSummary(
        run_id="RUN-XAAAAAAAAAAA",
        status="passed",
        quality_score=92.5,
        base_url="https://app.example.com",
        findings_by_severity={"medium": 1, "info": 2},
        report_url="https://reports.example.com/RUN-XAAAAAAAAAAA",
    )
    payload = render_teams_payload(summary)
    body = payload["attachments"][0]["content"]["body"]
    assert body[0]["text"].startswith("SentinelQA")
    actions = payload["attachments"][0]["content"]["actions"]
    assert actions[0]["url"].startswith("https://reports.example.com")


def test_teams_render_failed_uses_attention_color() -> None:
    summary = TeamsRunSummary(
        run_id="r",
        status="failed",
        quality_score=20.0,
        base_url="https://x",
    )
    body = render_teams_payload(summary)["attachments"][0]["content"]["body"]
    assert body[0]["color"] == "Attention"


def test_teams_dedup_skips_repeat(tmp_path) -> None:
    client = _FakeClient(responses=["1"])
    dedup = TeamsWebhookDeduper(path=tmp_path / "dedup.json", window_seconds=300)
    poster = TeamsPoster(
        webhook_url="https://x.webhook.office.com/webhookb2/a",
        client=client,
        dedup=dedup,
    )
    poster.post({"type": "message"})
    second = poster.post({"type": "message"})
    assert second == "deduped"
    assert len(client.calls) == 1


# --------------------------------------------------------------------------- #
# Discord
# --------------------------------------------------------------------------- #


def test_discord_constructor_rejects_http_webhook() -> None:
    with pytest.raises(DiscordPosterError):
        DiscordPoster(webhook_url="http://discord.com/api/webhooks/x/y")


def test_discord_post_happy_path() -> None:
    client = _FakeClient(responses=["{}"])
    poster = DiscordPoster(
        webhook_url="https://discord.com/api/webhooks/123/abc",
        client=client,
    )
    result = poster.post({"content": "hi"})
    assert result == "{}"
    url, payload = client.calls[0]
    assert "webhooks" in url
    assert payload["content"] == "hi"


def test_discord_render_includes_embed_colour() -> None:
    summary = DiscordRunSummary(
        run_id="r1",
        status="failed",
        quality_score=10.0,
        base_url="https://app.example.com",
        findings_by_severity={"critical": 2},
    )
    payload = render_discord_payload(summary)
    assert payload["embeds"][0]["color"] == 0xE74C3C
    assert any("Findings" in f["name"] for f in payload["embeds"][0]["fields"])


def test_discord_render_passed_returns_green() -> None:
    summary = DiscordRunSummary(
        run_id="r1",
        status="passed",
        quality_score=99.0,
        base_url="https://x",
    )
    payload = render_discord_payload(summary)
    assert payload["embeds"][0]["color"] == 0x2ECC71


def test_discord_dedup_skips_repeat(tmp_path) -> None:
    client = _FakeClient(responses=["{}"])
    dedup = DiscordWebhookDeduper(path=tmp_path / "d.json", window_seconds=300)
    poster = DiscordPoster(
        webhook_url="https://discord.com/api/webhooks/1/2",
        client=client,
        dedup=dedup,
    )
    poster.post({"content": "x"})
    second = poster.post({"content": "x"})
    assert second == "deduped"


# --------------------------------------------------------------------------- #
# PagerDuty
# --------------------------------------------------------------------------- #


def test_should_trigger_skips_when_score_missing() -> None:
    assert should_trigger(quality_score=None, threshold=80.0) is False


def test_should_trigger_pages_below_threshold() -> None:
    assert should_trigger(quality_score=60.0, threshold=80.0) is True
    assert should_trigger(quality_score=80.0, threshold=80.0) is False
    assert should_trigger(quality_score=85.0, threshold=80.0) is False


def test_build_trigger_payload_includes_required_fields() -> None:
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="RUN-X",
        quality_score=50.0,
        threshold=80.0,
        base_url="https://app.example.com",
        status="failed",
        findings_summary={"critical": 1},
        report_url="https://reports/x",
    )
    payload = build_trigger_payload(request)
    assert payload["event_action"] == "trigger"
    assert payload["routing_key"] == "rk"
    assert "sentinelqa:" in payload["dedup_key"]
    assert payload["payload"]["severity"] in {"critical", "error", "warning"}
    assert payload["links"][0]["href"] == "https://reports/x"


def test_build_trigger_payload_escalates_severity_with_gap() -> None:
    """30+ point gap → critical, 15+ → error, 5+ → warning, else info."""

    base = dict(routing_key="rk", run_id="r", threshold=80.0, base_url="", status="")
    crit = build_trigger_payload(PagerDutyTriggerRequest(quality_score=20.0, **base))["payload"][
        "severity"
    ]
    err = build_trigger_payload(PagerDutyTriggerRequest(quality_score=60.0, **base))["payload"][
        "severity"
    ]
    warn = build_trigger_payload(PagerDutyTriggerRequest(quality_score=72.0, **base))["payload"][
        "severity"
    ]
    info = build_trigger_payload(PagerDutyTriggerRequest(quality_score=79.0, **base))["payload"][
        "severity"
    ]
    assert crit == "critical"
    assert err == "error"
    assert warn == "warning"
    assert info == "info"


def test_build_resolve_payload_uses_resolve_action() -> None:
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=90.0,
        threshold=80.0,
        base_url="https://x",
        status="passed",
    )
    payload = build_resolve_payload(request)
    assert payload["event_action"] == "resolve"


def test_pagerduty_enqueue_skips_when_above_threshold() -> None:
    client = _FakeClient(responses=[])
    trigger = PagerDutyTrigger(client=client)
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=99.0,
        threshold=80.0,
        base_url="https://x",
        status="passed",
    )
    result = trigger.enqueue(request)
    assert result.event_action == "skip"
    assert client.calls == []


def test_pagerduty_enqueue_posts_when_below() -> None:
    client = _FakeClient(responses=[json.dumps({"message": "Event processed"})])
    trigger = PagerDutyTrigger(client=client)
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=40.0,
        threshold=80.0,
        base_url="https://x",
        status="failed",
    )
    result = trigger.enqueue(request)
    assert result.event_action == "trigger"
    assert client.calls
    assert "events.pagerduty.com" in client.calls[0][0]


def test_pagerduty_resolve_always_posts() -> None:
    client = _FakeClient(responses=[json.dumps({"message": "Event processed"})])
    trigger = PagerDutyTrigger(client=client)
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=99.0,
        threshold=80.0,
        base_url="https://x",
        status="passed",
    )
    result = trigger.resolve(request)
    assert result.event_action == "resolve"
    assert client.calls
