# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""OpenTelemetry span emission for the run lifecycle.

The tracer wraps a single context-manager API
``tracer.span(name, attrs)`` that:

* When OTel is enabled AND the ``opentelemetry`` SDK is importable,
  it emits a real span via the configured exporter.
* Otherwise it returns a no-op context manager so callers' code paths
  are identical regardless of installation state.

We keep the OTel SDK dependency optional: the import is lazy and any
ImportError simply demotes the tracer to a null implementation.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

SENTINELQA_OTEL_ENABLED_ENV: Final[str] = "SENTINELQA_OTEL_ENABLED"
OTLP_ENDPOINT_ENV: Final[str] = "OTEL_EXPORTER_OTLP_ENDPOINT"
OTLP_HEADERS_ENV: Final[str] = "OTEL_EXPORTER_OTLP_HEADERS"
SERVICE_NAME: Final[str] = "sentinelqa"

logger = logging.getLogger("sentinelqa.integrations.otel")

OtelStatus = Literal["disabled", "no-sdk", "enabled", "disabled-by-env"]


@dataclass(frozen=True, slots=True)
class _TracerHandle:
    """Holds the resolved tracer object + a human-readable status."""

    tracer: Any = None
    status: OtelStatus = "disabled"


def is_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return True iff the operator opted into OTel."""

    env_map = env if env is not None else dict(os.environ)
    value = env_map.get(SENTINELQA_OTEL_ENABLED_ENV, "").strip().lower()
    return value in ("1", "true", "yes", "on")


def build_span_attributes(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Stamp common ``service.*`` attributes on every span."""

    attrs: dict[str, Any] = {
        "service.name": SERVICE_NAME,
    }
    if extra:
        for key, value in extra.items():
            if isinstance(value, str | int | float | bool):
                attrs[key] = value
            elif value is not None:
                attrs[key] = str(value)
    return attrs


class NullTracer:
    """No-op tracer used when OTel is disabled or the SDK is missing."""

    status: OtelStatus = "disabled"

    @contextlib.contextmanager
    def span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Any]:
        _ = name, attributes
        yield None


@dataclass(frozen=True, slots=True)
class _RealTracer:
    handle: Any
    status: OtelStatus = "enabled"

    @contextlib.contextmanager
    def span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Any]:
        attrs = build_span_attributes(attributes)
        # Defer import so the no-op path stays fast.
        try:
            from opentelemetry.trace import Status, StatusCode  # type: ignore[import-not-found]
        except ImportError:
            yield None
            return
        with self.handle.start_as_current_span(name, attributes=attrs) as span:
            try:
                yield span
            except Exception as exc:
                if span is not None:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise


class SentinelTracer:
    """Public wrapper — pick between real / null tracer at construction."""

    def __init__(self, handle: Any | None, *, status: OtelStatus = "enabled") -> None:
        self._handle = handle
        self._status: OtelStatus = status

    @property
    def status(self) -> OtelStatus:
        return self._status

    def span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Any:
        if self._handle is None:
            return NullTracer().span(name, attributes)
        return _RealTracer(self._handle, status=self._status).span(name, attributes)


def enable_tracing(
    *,
    env: Mapping[str, str] | None = None,
    exporter: Any | None = None,
) -> SentinelTracer:
    """Resolve and return a tracer; never raises.

    Resolution chain:
      1. If env opt-out → return null.
      2. If ``opentelemetry`` package is missing → return null with
         ``status="no-sdk"`` and a single warning.
      3. Else build a TracerProvider with the OTLP/HTTP exporter
         (the endpoint comes from :data:`OTLP_ENDPOINT_ENV`).
    """

    env_map = env if env is not None else dict(os.environ)
    if not is_enabled(env_map):
        return SentinelTracer(handle=None, status="disabled-by-env")

    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
        )
    except ImportError as exc:
        logger.warning("OTel requested but opentelemetry-sdk is not installed: %s", exc)
        return SentinelTracer(handle=None, status="no-sdk")

    if exporter is None:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )
        except ImportError as exc:
            logger.warning(
                "OTLP/HTTP exporter not installed; tracing remains no-op: %s",
                exc,
            )
            return SentinelTracer(handle=None, status="no-sdk")
        exporter = OTLPSpanExporter(
            endpoint=env_map.get(OTLP_ENDPOINT_ENV, "http://localhost:4318/v1/traces"),
        )

    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return SentinelTracer(handle=trace.get_tracer(SERVICE_NAME), status="enabled")


__all__ = [
    "OTLP_ENDPOINT_ENV",
    "OTLP_HEADERS_ENV",
    "OtelStatus",
    "NullTracer",
    "SENTINELQA_OTEL_ENABLED_ENV",
    "SentinelTracer",
    "build_span_attributes",
    "enable_tracing",
    "is_enabled",
]
