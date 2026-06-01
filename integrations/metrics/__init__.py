# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Metrics adapters (v1.5.0).

Three thin push-adapters that translate a SentinelQA run into a
provider-specific metric envelope and POST it via the shared
:mod:`integrations._http` client.

* :mod:`integrations.metrics.datadog` — Datadog Metrics V2.
* :mod:`integrations.metrics.newrelic` — New Relic Metric API.
* :mod:`integrations.metrics.honeycomb` — Honeycomb Events.

A shared :func:`extract_run_metrics` helper distils ``score.json`` +
``run.json`` + ``module-results/*.json`` into a normalised
:class:`RunMetrics` tuple every adapter consumes.
"""

from __future__ import annotations

from integrations.metrics.builder import (
    RunMetrics,
    extract_run_metrics,
)
from integrations.metrics.datadog import (
    DATADOG_API_KEY_ENV,
    DatadogError,
    DatadogPusher,
    build_datadog_payload,
)
from integrations.metrics.honeycomb import (
    HONEYCOMB_API_KEY_ENV,
    HoneycombError,
    HoneycombPusher,
    build_honeycomb_event,
)
from integrations.metrics.newrelic import (
    NEWRELIC_LICENSE_KEY_ENV,
    NewRelicError,
    NewRelicPusher,
    build_newrelic_payload,
)

__all__ = [
    "DATADOG_API_KEY_ENV",
    "DatadogError",
    "DatadogPusher",
    "HONEYCOMB_API_KEY_ENV",
    "HoneycombError",
    "HoneycombPusher",
    "NEWRELIC_LICENSE_KEY_ENV",
    "NewRelicError",
    "NewRelicPusher",
    "RunMetrics",
    "build_datadog_payload",
    "build_honeycomb_event",
    "build_newrelic_payload",
    "extract_run_metrics",
]
