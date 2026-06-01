# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Extra coverage for the v1.5.0 notifiers, metrics, and OTel."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from integrations._http import HttpClient, IntegrationHttpError
from integrations.discord import (
    DiscordPoster,
    DiscordPosterError,
    DiscordWebhookDeduper,
)
from integrations.discord import poster as discord_mod
from integrations.metrics.builder import RunMetrics
from integrations.otel import (
    SENTINELQA_OTEL_ENABLED_ENV,
    NullTracer,
    SentinelTracer,
    enable_tracing,
)
from integrations.pagerduty import (
    PagerDutyError,
    PagerDutyTrigger,
    PagerDutyTriggerRequest,
)
from integrations.teams import (
    TeamsPoster,
    TeamsPosterError,
    TeamsWebhookDeduper,
)
from integrations.teams import poster as teams_mod


class _FailingClient(HttpClient):
    def __init__(self, *, exc: Exception) -> None:
        super().__init__()
        self._exc = exc

    def post_text(self, url: str, payload: Mapping[str, Any]) -> str:
        raise self._exc


# --------------------------------------------------------------------------- #
# Webhook redaction helpers
# --------------------------------------------------------------------------- #


def test_teams_redact_webhook_strips_secret_path() -> None:
    redacted = teams_mod._redact_webhook("https://tenant.webhook.office.com/webhookb2/AAA/BBB")
    assert "AAA" not in redacted
    assert "redacted" in redacted.lower()


def test_discord_redact_webhook_strips_secret_path() -> None:
    redacted = discord_mod._redact_webhook("https://discord.com/api/webhooks/1234567890/AAA")
    assert "AAA" not in redacted
    assert "redacted" in redacted.lower()


def test_teams_redact_webhook_returns_input_when_marker_absent() -> None:
    out = teams_mod._redact_webhook("https://tenant.webhook.office.com/other/x")
    assert "other" in out


def test_discord_redact_webhook_returns_input_when_marker_absent() -> None:
    out = discord_mod._redact_webhook("https://discord.com/api/foo")
    assert "foo" in out


# --------------------------------------------------------------------------- #
# Notifier error propagation
# --------------------------------------------------------------------------- #


def test_teams_poster_wraps_http_error() -> None:
    poster = TeamsPoster(
        webhook_url="https://x.webhook.office.com/webhookb2/a",
        client=_FailingClient(exc=IntegrationHttpError("network down")),
    )
    with pytest.raises(TeamsPosterError):
        poster.post({"type": "message"})


def test_discord_poster_wraps_http_error() -> None:
    poster = DiscordPoster(
        webhook_url="https://discord.com/api/webhooks/1/2",
        client=_FailingClient(exc=IntegrationHttpError("network down")),
    )
    with pytest.raises(DiscordPosterError):
        poster.post({"content": "x"})


def test_pagerduty_wraps_http_error() -> None:
    trigger = PagerDutyTrigger(client=_FailingClient(exc=IntegrationHttpError("ratelimit")))
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=50.0,
        threshold=80.0,
        base_url="https://x",
        status="failed",
    )
    with pytest.raises(PagerDutyError):
        trigger.enqueue(request)


# --------------------------------------------------------------------------- #
# Dedup cache round-trips
# --------------------------------------------------------------------------- #


def test_teams_dedup_records_and_round_trips(tmp_path: Path) -> None:
    dedup = TeamsWebhookDeduper(path=tmp_path / "dedup.json", window_seconds=60)
    payload = {"a": 1}
    assert dedup.is_duplicate(payload=payload, webhook_url="https://x") is False
    dedup.record(payload=payload, webhook_url="https://x")
    assert dedup.is_duplicate(payload=payload, webhook_url="https://x") is True


def test_discord_dedup_handles_corrupt_state_file(tmp_path: Path) -> None:
    """A malformed dedup cache must degrade to ``no record``."""

    cache = tmp_path / "dedup.json"
    cache.write_text("not json", encoding="utf-8")
    dedup = DiscordWebhookDeduper(path=cache, window_seconds=60)
    assert dedup.is_duplicate(payload={"a": 1}, webhook_url="https://x") is False


# --------------------------------------------------------------------------- #
# Metrics edge paths
# --------------------------------------------------------------------------- #


def test_extract_run_metrics_handles_missing_finished_at(tmp_path: Path) -> None:
    from integrations.metrics.builder import extract_run_metrics

    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "run_id": "RUN-X",
                "status": "passed",
                "target": {"base_url": "x", "host": "x"},
                "started_at": "not-a-date",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    metrics = extract_run_metrics(tmp_path)
    assert metrics.duration_ms == 0


def test_extract_run_metrics_handles_malformed_module_result(tmp_path: Path) -> None:
    from integrations.metrics.builder import extract_run_metrics

    (tmp_path / "run.json").write_text(
        json.dumps(
            {
                "run_id": "RUN-X",
                "status": "passed",
                "target": {"host": "x"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "findings.json").write_text(
        json.dumps({"findings": [{"id": "FND-1", "severity": "info"}]}),
        encoding="utf-8",
    )
    mr = tmp_path / "module-results"
    mr.mkdir()
    (mr / "broken.json").write_text("not json", encoding="utf-8")
    metrics = extract_run_metrics(tmp_path)
    assert metrics.module_durations_ms == {}
    assert metrics.findings_by_severity["info"] == 1


# --------------------------------------------------------------------------- #
# OTel
# --------------------------------------------------------------------------- #


def test_null_tracer_yields_none() -> None:
    tracer = NullTracer()
    with tracer.span("x", {"k": "v"}) as span:
        assert span is None


def test_sentinel_tracer_status_when_null_handle() -> None:
    tracer = SentinelTracer(handle=None, status="disabled")
    assert tracer.status == "disabled"


def test_enable_tracing_no_sdk_returns_clean_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``opentelemetry`` is missing, ``enable_tracing`` returns a null tracer."""

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("opentelemetry"):
            raise ImportError(f"simulated: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    tracer = enable_tracing(env={SENTINELQA_OTEL_ENABLED_ENV: "1"})
    assert tracer.status == "no-sdk"
    with tracer.span("x") as span:
        assert span is None


# --------------------------------------------------------------------------- #
# Pagerduty resolve
# --------------------------------------------------------------------------- #


def test_pagerduty_resolve_propagates_http_error() -> None:
    trigger = PagerDutyTrigger(client=_FailingClient(exc=IntegrationHttpError("oops")))
    request = PagerDutyTriggerRequest(
        routing_key="rk",
        run_id="r",
        quality_score=99.0,
        threshold=80.0,
        base_url="https://x",
        status="passed",
    )
    with pytest.raises(PagerDutyError):
        trigger.resolve(request)


# --------------------------------------------------------------------------- #
# RunMetrics value object
# --------------------------------------------------------------------------- #


def test_run_metrics_default_dicts_are_empty() -> None:
    metrics = RunMetrics(
        run_id="r",
        status="passed",
        quality_score=None,
        target_host="x",
        started_at="2026-06-01T00:00:00+00:00",
        duration_ms=0,
    )
    assert metrics.findings_by_severity == {}
    assert metrics.module_durations_ms == {}
