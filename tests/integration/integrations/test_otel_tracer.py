# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the OpenTelemetry tracer wrapper."""

from __future__ import annotations

import contextlib
from typing import Any

import pytest
from integrations.otel import (
    SENTINELQA_OTEL_ENABLED_ENV,
    NullTracer,
    SentinelTracer,
    build_span_attributes,
    enable_tracing,
    is_enabled,
)


def test_is_enabled_returns_false_by_default() -> None:
    assert is_enabled({}) is False


def test_is_enabled_accepts_canonical_truthy_values() -> None:
    for value in ("1", "true", "YES", "on"):
        assert is_enabled({SENTINELQA_OTEL_ENABLED_ENV: value}) is True


def test_is_enabled_rejects_other_values() -> None:
    for value in ("0", "false", "no", "off", "x"):
        assert is_enabled({SENTINELQA_OTEL_ENABLED_ENV: value}) is False


def test_build_span_attributes_includes_service_name() -> None:
    attrs = build_span_attributes({"run_id": "RUN-X", "score": 92.5})
    assert attrs["service.name"] == "sentinelqa"
    assert attrs["run_id"] == "RUN-X"
    assert attrs["score"] == 92.5


def test_build_span_attributes_drops_none() -> None:
    attrs = build_span_attributes({"k": None})
    assert "k" not in attrs


def test_null_tracer_span_is_a_no_op_context_manager() -> None:
    tracer = NullTracer()
    with tracer.span("foo", {"k": "v"}) as span:
        assert span is None


def test_enable_tracing_returns_null_when_env_disabled() -> None:
    tracer = enable_tracing(env={})
    assert tracer.status == "disabled-by-env"
    with tracer.span("foo") as span:
        assert span is None


def test_enable_tracing_returns_no_sdk_when_opentelemetry_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate ``import opentelemetry`` failing — tracer falls back cleanly."""

    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError(f"simulated: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    tracer = enable_tracing(env={SENTINELQA_OTEL_ENABLED_ENV: "1"})
    assert tracer.status == "no-sdk"


def test_sentinel_tracer_status_property() -> None:
    tracer = SentinelTracer(handle=None, status="disabled")
    assert tracer.status == "disabled"


def test_sentinel_tracer_with_handle_runs_without_raising() -> None:
    """When a non-null handle is provided, ``span()`` must not raise.

    The internal :mod:`opentelemetry.trace` import is lazy and may be
    absent in the test environment; in that case ``_RealTracer.span``
    yields ``None`` and returns cleanly. The contract we verify is
    that callers can wrap their code in ``with tracer.span(...)``
    regardless of installation state.
    """

    class _FakeHandle:
        @contextlib.contextmanager
        def start_as_current_span(self, name: str, attributes: dict[str, Any]):
            _ = name, attributes
            yield None

    tracer = SentinelTracer(handle=_FakeHandle(), status="enabled")
    with tracer.span("audit.discover", {"run_id": "RUN-X"}):
        pass
