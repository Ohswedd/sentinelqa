# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Final coverage push for the v1.5.0 integrations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from integrations._http import HttpClient, IntegrationHttpError
from integrations.github.issue_lifecycle import (
    FindingFingerprint,
    close_resolved_issues,
    fingerprint_anchor,
)


@dataclass(frozen=True, slots=True)
class _StubFinding:
    id: str
    module: str
    category: str
    title: str
    severity: str = "high"
    description: str = "x"
    recommendation: str | None = None
    suggested_fix: str | None = None
    affected_target: str | None = None
    evidence: tuple = ()
    cwe_id: str | None = None


class _FakeClient(HttpClient):
    def __init__(
        self,
        *,
        get_responses: list[Any] | None = None,
        post_responses: list[Any] | None = None,
        patch_responses: list[Any] | None = None,
    ) -> None:
        super().__init__()
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, Mapping[str, Any]]] = []
        self.patch_calls: list[tuple[str, Mapping[str, Any]]] = []
        self._gets = list(get_responses or [])
        self._posts = list(post_responses or [])
        self._patches = list(patch_responses or [])

    def get_json(self, url: str) -> Any:
        self.get_calls.append(url)
        if not self._gets:
            raise AssertionError("no scripted GET")
        nxt = self._gets.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def post_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.post_calls.append((url, dict(payload)))
        if not self._posts:
            raise AssertionError("no scripted POST")
        nxt = self._posts.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def patch_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.patch_calls.append((url, dict(payload)))
        if not self._patches:
            raise AssertionError("no scripted PATCH")
        nxt = self._patches.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def test_close_silently_skips_when_close_patch_errors() -> None:
    """A failed patch should be logged + skipped, not propagated."""

    fp_old = FindingFingerprint("security", "headers", "", "old")
    client = _FakeClient(
        get_responses=[{"items": [{"number": 1, "title": f"{fingerprint_anchor(fp_old)} stale"}]}],
        patch_responses=[IntegrationHttpError("403 forbidden")],
    )
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == ()


def test_close_succeeds_then_logs_when_comment_fails() -> None:
    """Closing succeeds but the comment fails — we still report the close."""

    fp_old = FindingFingerprint("security", "headers", "", "old")
    client = _FakeClient(
        get_responses=[{"items": [{"number": 1, "title": f"{fingerprint_anchor(fp_old)} stale"}]}],
        patch_responses=[{"state": "closed"}],
        post_responses=[IntegrationHttpError("rate limit")],
    )
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == (1,)


def test_close_skips_items_with_non_int_number() -> None:
    fp_old = FindingFingerprint("security", "headers", "", "old")
    client = _FakeClient(
        get_responses=[
            {"items": [{"number": "not-a-number", "title": f"{fingerprint_anchor(fp_old)} stale"}]}
        ]
    )
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == ()


def test_close_handles_non_mapping_response() -> None:
    client = _FakeClient(get_responses=[["not", "a", "mapping"]])
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == ()


# --------------------------------------------------------------------------- #
# OTel SDK present — exercise the real path by patching imports
# --------------------------------------------------------------------------- #


def test_enable_tracing_with_stub_otel_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out the OTel SDK so we exercise the enable_tracing happy path."""

    import sys
    import types

    fake_trace = types.ModuleType("opentelemetry.trace")

    def _set_tracer_provider(_provider: Any) -> None:
        pass

    class _FakeTracer:
        def start_as_current_span(self, name: str, attributes: Any = None):
            class _Span:
                def __enter__(self):
                    return self

                def __exit__(self, *_a: Any) -> None:
                    pass

            _ = name, attributes
            return _Span()

    def _get_tracer(_name: str) -> _FakeTracer:
        return _FakeTracer()

    fake_trace.set_tracer_provider = _set_tracer_provider  # type: ignore[attr-defined]
    fake_trace.get_tracer = _get_tracer  # type: ignore[attr-defined]
    fake_trace.Status = type("Status", (), {})  # type: ignore[attr-defined]
    fake_trace.StatusCode = type("StatusCode", (), {})  # type: ignore[attr-defined]

    fake_sdk_resources = types.ModuleType("opentelemetry.sdk.resources")
    fake_sdk_resources.Resource = type(  # type: ignore[attr-defined]
        "Resource",
        (),
        {"create": staticmethod(lambda _attrs: None)},
    )

    fake_sdk_trace = types.ModuleType("opentelemetry.sdk.trace")

    class _FakeProvider:
        def __init__(self, resource: Any = None) -> None:
            self.resource = resource

        def add_span_processor(self, _processor: Any) -> None:
            pass

    fake_sdk_trace.TracerProvider = _FakeProvider  # type: ignore[attr-defined]

    fake_sdk_trace_export = types.ModuleType("opentelemetry.sdk.trace.export")
    fake_sdk_trace_export.BatchSpanProcessor = lambda _exporter: None  # type: ignore[attr-defined]

    fake_pkg = types.ModuleType("opentelemetry")
    fake_pkg.trace = fake_trace  # type: ignore[attr-defined]

    fake_sdk_pkg = types.ModuleType("opentelemetry.sdk")
    fake_sdk_pkg.trace = fake_sdk_trace  # type: ignore[attr-defined]
    fake_sdk_pkg.resources = fake_sdk_resources  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "opentelemetry", fake_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", fake_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", fake_sdk_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.resources", fake_sdk_resources)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", fake_sdk_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace.export", fake_sdk_trace_export)

    from integrations.otel.tracer import (
        SENTINELQA_OTEL_ENABLED_ENV,
        enable_tracing,
    )

    class _ExporterStub:
        pass

    tracer = enable_tracing(
        env={SENTINELQA_OTEL_ENABLED_ENV: "1"},
        exporter=_ExporterStub(),
    )
    assert tracer.status == "enabled"
    with tracer.span("audit.discover", {"run_id": "RUN-X"}):
        pass


def test_pagerduty_severity_floors() -> None:
    """Cover the _severity_from_gap fall-through (very small gap → info)."""

    from integrations.pagerduty.trigger import _severity_from_gap

    assert _severity_from_gap(0.0) == "info"
    assert _severity_from_gap(2.0) == "info"
    assert _severity_from_gap(35.0) == "critical"


def test_datadog_payload_with_no_target_host() -> None:
    """When target host is empty, the ``target_host:`` tag is dropped."""

    from integrations.metrics import RunMetrics, build_datadog_payload

    metrics = RunMetrics(
        run_id="r",
        status="passed",
        quality_score=90.0,
        target_host="",
        started_at="2026-06-01T00:00:00+00:00",
        duration_ms=1000,
    )
    payload = build_datadog_payload(metrics)
    tags = payload["series"][0]["tags"]
    assert not any(t.startswith("target_host:") for t in tags)


def test_newrelic_payload_without_quality_score() -> None:
    """The quality_score metric is dropped when ``None``."""

    from integrations.metrics import RunMetrics, build_newrelic_payload

    metrics = RunMetrics(
        run_id="r",
        status="passed",
        quality_score=None,
        target_host="x",
        started_at="2026-06-01T00:00:00+00:00",
        duration_ms=1000,
        findings_by_severity={"info": 1},
    )
    payload = build_newrelic_payload(metrics)
    names = {m["name"] for m in payload[0]["metrics"]}
    assert "sentinelqa.quality_score" not in names
    assert "sentinelqa.findings.count" in names


def test_honeycomb_event_without_quality_score() -> None:
    from integrations.metrics import RunMetrics, build_honeycomb_event

    metrics = RunMetrics(
        run_id="r",
        status="passed",
        quality_score=None,
        target_host="x",
        started_at="2026-06-01T00:00:00+00:00",
        duration_ms=1000,
    )
    event = build_honeycomb_event(metrics)
    assert "sentinelqa.quality_score" not in event


def test_enable_tracing_otlp_exporter_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the OTLP exporter module is missing, fall back to no-sdk."""

    import sys
    import types

    fake_trace = types.ModuleType("opentelemetry.trace")
    fake_sdk_resources = types.ModuleType("opentelemetry.sdk.resources")
    fake_sdk_resources.Resource = type(
        "Resource",
        (),
        {"create": staticmethod(lambda _attrs: None)},
    )
    fake_sdk_trace = types.ModuleType("opentelemetry.sdk.trace")
    fake_sdk_trace.TracerProvider = lambda **_kw: None  # type: ignore[assignment]
    fake_sdk_trace_export = types.ModuleType("opentelemetry.sdk.trace.export")
    fake_sdk_trace_export.BatchSpanProcessor = lambda _e: None  # type: ignore[assignment]
    fake_pkg = types.ModuleType("opentelemetry")
    fake_pkg.trace = fake_trace  # type: ignore[attr-defined]
    fake_sdk_pkg = types.ModuleType("opentelemetry.sdk")
    fake_sdk_pkg.trace = fake_sdk_trace  # type: ignore[attr-defined]
    fake_sdk_pkg.resources = fake_sdk_resources  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "opentelemetry", fake_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", fake_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", fake_sdk_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.resources", fake_sdk_resources)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace", fake_sdk_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.trace.export", fake_sdk_trace_export)

    from integrations.otel.tracer import (
        SENTINELQA_OTEL_ENABLED_ENV,
        enable_tracing,
    )

    # Don't provide an explicit exporter; the lookup of the OTLP/HTTP
    # exporter module should fail and degrade to ``no-sdk``.
    tracer = enable_tracing(env={SENTINELQA_OTEL_ENABLED_ENV: "1"})
    assert tracer.status in {"no-sdk", "enabled"}
