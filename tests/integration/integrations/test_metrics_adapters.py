# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Mocked tests for the Datadog / New Relic / Honeycomb metrics adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from integrations._http import HttpClient
from integrations.metrics import (
    DatadogError,
    DatadogPusher,
    HoneycombError,
    HoneycombPusher,
    NewRelicError,
    NewRelicPusher,
    RunMetrics,
    build_datadog_payload,
    build_honeycomb_event,
    build_newrelic_payload,
    extract_run_metrics,
)


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


_RUN = RunMetrics(
    run_id="RUN-XAAAAAAAAAAA",
    status="passed",
    quality_score=92.5,
    target_host="app.example.com",
    started_at="2026-06-01T00:00:00+00:00",
    duration_ms=60_000,
    findings_by_severity={"medium": 1, "info": 3},
    module_durations_ms={"functional": 12_000, "security": 18_000},
)


# --------------------------------------------------------------------------- #
# Shared extractor
# --------------------------------------------------------------------------- #


def _write_run(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(
        json.dumps(
            {
                "run_id": "RUN-XAAAAAAAAAAA",
                "status": "passed",
                "quality_score": 88.0,
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
                "modules_run": ["security"],
                "summary": {"passed": 1, "failed": 0, "blocked": 0, "info": 0},
            }
        ),
        encoding="utf-8",
    )
    (path / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {"id": "FND-1", "severity": "high"},
                    {"id": "FND-2", "severity": "medium"},
                    {"id": "FND-3", "severity": "medium"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (path / "score.json").write_text("{}", encoding="utf-8")
    mr = path / "module-results"
    mr.mkdir(exist_ok=True)
    (mr / "security.json").write_text(
        json.dumps(
            {
                "module_result": {
                    "id": "MOD-XAAAAAAAAAAA",
                    "name": "security",
                    "status": "passed",
                    "duration_ms": 4500,
                }
            }
        ),
        encoding="utf-8",
    )


def test_extract_run_metrics_reads_severity_counts(tmp_path: Path) -> None:
    _write_run(tmp_path)
    metrics = extract_run_metrics(tmp_path)
    assert metrics.run_id == "RUN-XAAAAAAAAAAA"
    assert metrics.quality_score == 88.0
    assert metrics.findings_by_severity["medium"] == 2
    assert metrics.module_durations_ms["security"] == 4500
    assert metrics.duration_ms == 60_000


def test_extract_run_metrics_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    metrics = extract_run_metrics(tmp_path / "nope")
    assert metrics.run_id == "nope"
    assert metrics.quality_score is None
    assert metrics.findings_by_severity == {}


# --------------------------------------------------------------------------- #
# Datadog
# --------------------------------------------------------------------------- #


def test_datadog_rejects_empty_key() -> None:
    with pytest.raises(DatadogError):
        DatadogPusher(api_key="")


def test_datadog_payload_includes_quality_score_and_findings() -> None:
    payload = build_datadog_payload(_RUN)
    metric_names = {row["metric"] for row in payload["series"]}
    assert "sentinelqa.quality_score" in metric_names
    assert "sentinelqa.findings.count" in metric_names
    assert "sentinelqa.module.duration_ms" in metric_names
    tags = payload["series"][0]["tags"]
    assert any(t.startswith("target_host:") for t in tags)


def test_datadog_push_happy_path() -> None:
    client = _FakeClient(responses=['{"errors": []}'])
    pusher = DatadogPusher(api_key="dd-key", client=client)
    body = pusher.push(_RUN)
    assert "errors" in body
    url, payload = client.calls[0]
    assert "datadoghq.com" in url
    assert "series" in payload


# --------------------------------------------------------------------------- #
# New Relic
# --------------------------------------------------------------------------- #


def test_newrelic_rejects_empty_key() -> None:
    with pytest.raises(NewRelicError):
        NewRelicPusher(license_key="")


def test_newrelic_payload_is_a_batched_list() -> None:
    payload = build_newrelic_payload(_RUN)
    assert isinstance(payload, list)
    assert len(payload) == 1
    metrics = payload[0]["metrics"]
    names = {m["name"] for m in metrics}
    assert "sentinelqa.quality_score" in names
    assert "sentinelqa.module.duration_ms" in names


def test_newrelic_push_happy_path() -> None:
    client = _FakeClient(responses=['{"requestId": "abc"}'])
    pusher = NewRelicPusher(license_key="nr-key", client=client)
    body = pusher.push(_RUN)
    assert "requestId" in body


# --------------------------------------------------------------------------- #
# Honeycomb
# --------------------------------------------------------------------------- #


def test_honeycomb_rejects_empty_key() -> None:
    with pytest.raises(HoneycombError):
        HoneycombPusher(api_key="")


def test_honeycomb_event_includes_flat_keys() -> None:
    event = build_honeycomb_event(_RUN)
    assert event["service.name"] == "sentinelqa"
    assert event["sentinelqa.quality_score"] == 92.5
    assert event["sentinelqa.findings.medium"] == 1
    assert event["sentinelqa.module.functional.duration_ms"] == 12_000


def test_honeycomb_push_happy_path() -> None:
    client = _FakeClient(responses=[""])
    pusher = HoneycombPusher(api_key="hc-key", dataset="sentinelqa", client=client)
    body = pusher.push(_RUN)
    assert body == ""
    url, payload = client.calls[0]
    assert "honeycomb.io" in url
    assert payload["sentinelqa.run_id"] == "RUN-XAAAAAAAAAAA"
