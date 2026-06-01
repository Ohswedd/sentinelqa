# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Coverage for the CLI `main` entry points of v1.5.0 notifiers + extras."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

from integrations._http import HttpClient


class _FakeClient(HttpClient):
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
# Teams CLI
# --------------------------------------------------------------------------- #


def test_teams_main_requires_webhook(tmp_path: Path) -> None:
    """Empty webhook yields exit 2."""

    from integrations.teams.poster import main

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    rc = main(["--payload-file", str(payload_path)])
    assert rc == 2


def test_teams_main_handles_unreadable_payload(tmp_path: Path) -> None:
    from integrations.teams.poster import main

    rc = main(
        [
            "--webhook-url",
            "https://x.webhook.office.com/webhookb2/a",
            "--payload-file",
            str(tmp_path / "missing.json"),
        ]
    )
    assert rc == 2


def test_teams_main_propagates_poster_error(tmp_path: Path, monkeypatch) -> None:
    from integrations.teams import poster as teams_mod

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    def boom(**_kwargs: Any) -> str:
        raise teams_mod.TeamsPosterError("simulated")

    monkeypatch.setattr(teams_mod, "post_payload", boom)
    rc = teams_mod.main(
        [
            "--webhook-url",
            "https://x.webhook.office.com/webhookb2/a",
            "--payload-file",
            str(payload_path),
        ]
    )
    assert rc == 1


def test_teams_main_happy_path(tmp_path: Path, monkeypatch) -> None:
    from integrations.teams import poster as teams_mod

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    monkeypatch.setattr(teams_mod, "post_payload", lambda **_kw: "1")
    rc = teams_mod.main(
        [
            "--webhook-url",
            "https://x.webhook.office.com/webhookb2/a",
            "--payload-file",
            str(payload_path),
        ]
    )
    assert rc == 0


# --------------------------------------------------------------------------- #
# Discord CLI
# --------------------------------------------------------------------------- #


def test_discord_main_requires_webhook(tmp_path: Path) -> None:
    from integrations.discord.poster import main

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    rc = main(["--payload-file", str(payload_path)])
    assert rc == 2


def test_discord_main_handles_unreadable_payload(tmp_path: Path) -> None:
    from integrations.discord.poster import main

    rc = main(
        [
            "--webhook-url",
            "https://discord.com/api/webhooks/1/2",
            "--payload-file",
            str(tmp_path / "missing.json"),
        ]
    )
    assert rc == 2


def test_discord_main_propagates_poster_error(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord import poster as discord_mod

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    def boom(**_kwargs: Any) -> str:
        raise discord_mod.DiscordPosterError("simulated")

    monkeypatch.setattr(discord_mod, "post_payload", boom)
    rc = discord_mod.main(
        [
            "--webhook-url",
            "https://discord.com/api/webhooks/1/2",
            "--payload-file",
            str(payload_path),
        ]
    )
    assert rc == 1


def test_discord_main_happy_path(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord import poster as discord_mod

    payload_path = tmp_path / "p.json"
    payload_path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    monkeypatch.setattr(discord_mod, "post_payload", lambda **_kw: "ok")
    rc = discord_mod.main(
        [
            "--webhook-url",
            "https://discord.com/api/webhooks/1/2",
            "--payload-file",
            str(payload_path),
        ]
    )
    assert rc == 0


# --------------------------------------------------------------------------- #
# PagerDuty CLI
# --------------------------------------------------------------------------- #


def test_pagerduty_main_requires_routing_key() -> None:
    from integrations.pagerduty.trigger import main

    rc = main(
        [
            "--run-id",
            "RUN-X",
            "--threshold",
            "80",
        ]
    )
    assert rc == 2


def test_pagerduty_main_happy_path(monkeypatch) -> None:
    from integrations.pagerduty import trigger as pd_mod

    class _StubTrigger:
        def enqueue(self, request):
            return pd_mod.PagerDutyTriggerResult(
                event_action="trigger",
                dedup_key="sentinelqa:x",
                detail="enqueued",
            )

        def resolve(self, request):
            return pd_mod.PagerDutyTriggerResult(
                event_action="resolve",
                dedup_key="sentinelqa:x",
                detail="resolved",
            )

    monkeypatch.setattr(pd_mod, "PagerDutyTrigger", lambda **_kw: _StubTrigger())
    rc = pd_mod.main(
        [
            "--routing-key",
            "rk",
            "--run-id",
            "RUN-X",
            "--quality-score",
            "10",
            "--threshold",
            "80",
            "--base-url",
            "https://app.example.com",
        ]
    )
    assert rc == 0


def test_pagerduty_main_propagates_error(monkeypatch) -> None:
    from integrations.pagerduty import trigger as pd_mod

    class _BrokenTrigger:
        def enqueue(self, request):
            raise pd_mod.PagerDutyError("simulated")

        def resolve(self, request):
            raise pd_mod.PagerDutyError("simulated")

    monkeypatch.setattr(pd_mod, "PagerDutyTrigger", lambda **_kw: _BrokenTrigger())
    rc = pd_mod.main(
        [
            "--routing-key",
            "rk",
            "--run-id",
            "RUN-X",
            "--quality-score",
            "10",
            "--threshold",
            "80",
        ]
    )
    assert rc == 1


def test_pagerduty_resolve_flag() -> None:
    """The --resolve flag must route through ``trigger.resolve``."""

    from integrations.pagerduty import trigger as pd_mod

    with patch.object(pd_mod, "PagerDutyTrigger") as mock_trigger_cls:
        mock_instance = mock_trigger_cls.return_value
        mock_instance.resolve.return_value = pd_mod.PagerDutyTriggerResult(
            event_action="resolve",
            dedup_key="sentinelqa:x",
            detail="resolved",
        )
        rc = pd_mod.main(
            [
                "--routing-key",
                "rk",
                "--run-id",
                "RUN-X",
                "--threshold",
                "80",
                "--resolve",
            ]
        )
    assert rc == 0
    mock_instance.resolve.assert_called_once()


# --------------------------------------------------------------------------- #
# OTel extras (build_span_attributes coercion paths)
# --------------------------------------------------------------------------- #


def test_build_span_attributes_coerces_complex_values() -> None:
    from integrations.otel.tracer import build_span_attributes

    attrs = build_span_attributes(
        {
            "int": 1,
            "float": 1.5,
            "bool": True,
            "str": "x",
            "list": [1, 2],  # not primitive — coerced via str()
        }
    )
    assert attrs["int"] == 1
    assert attrs["bool"] is True
    assert attrs["str"] == "x"
    assert attrs["list"] == "[1, 2]"


def test_enable_tracing_without_env_returns_disabled() -> None:
    from integrations.otel.tracer import enable_tracing

    tracer = enable_tracing(env={})
    assert tracer.status == "disabled-by-env"
