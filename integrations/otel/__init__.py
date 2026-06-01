# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""OpenTelemetry traces export (v1.5.0).

Emit OTLP/HTTP spans for each step of the run lifecycle so SentinelQA
plugs into the team's existing observability stack. Activation is
opt-in via :func:`enable_tracing`; when disabled the helpers return
a no-op tracer so the lifecycle is unaffected.

The implementation uses the ``opentelemetry`` package when present;
when not, it returns a no-op `NullTracer`. We do not add
``opentelemetry-sdk`` as a hard runtime dep — installation is an
``opt-in`` extra (``pip install 'sentinelqa-engine[otel]'``).
"""

from __future__ import annotations

from integrations.otel.tracer import (
    OTLP_ENDPOINT_ENV,
    OTLP_HEADERS_ENV,
    SENTINELQA_OTEL_ENABLED_ENV,
    NullTracer,
    OtelStatus,
    SentinelTracer,
    build_span_attributes,
    enable_tracing,
    is_enabled,
)

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
