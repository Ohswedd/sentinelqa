# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Datadog Metrics V2 push adapter."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from typing import Any, Final

from integrations._http import AuthHeader, HttpClient, IntegrationHttpError, RetrySpec
from integrations.metrics.builder import RunMetrics

DATADOG_API_KEY_ENV: Final[str] = "SENTINELQA_DATADOG_API_KEY"
DATADOG_DEFAULT_SITE: Final[str] = "datadoghq.com"

logger = logging.getLogger("sentinelqa.integrations.datadog")


class DatadogError(RuntimeError):
    """Raised when a Datadog push cannot complete safely."""


def _series(
    metric: str,
    *,
    value: float,
    timestamp: int,
    tags: Sequence[str],
    metric_type: int = 3,  # 3 = gauge in the v2 enum
) -> dict[str, Any]:
    return {
        "metric": metric,
        "type": metric_type,
        "points": [{"timestamp": timestamp, "value": value}],
        "tags": list(tags),
    }


def _timestamp_from_iso(iso: str) -> int:
    from datetime import datetime

    try:
        return int(datetime.fromisoformat(iso).timestamp())
    except ValueError:
        return 0


def build_datadog_payload(metrics: RunMetrics) -> dict[str, Any]:
    """Build the ``/api/v2/series`` payload."""

    timestamp = _timestamp_from_iso(metrics.started_at) or 0
    tags = [
        f"target_host:{metrics.target_host}" if metrics.target_host else "",
        f"status:{metrics.status}" if metrics.status else "",
        f"run_id:{metrics.run_id}" if metrics.run_id else "",
        "sentinelqa:audit",
    ]
    tags = [t for t in tags if t]

    series: list[dict[str, Any]] = []
    if metrics.quality_score is not None:
        series.append(
            _series(
                "sentinelqa.quality_score",
                value=metrics.quality_score,
                timestamp=timestamp,
                tags=tags,
            )
        )
    series.append(
        _series(
            "sentinelqa.duration_ms",
            value=metrics.duration_ms,
            timestamp=timestamp,
            tags=tags,
        )
    )
    for severity, count in metrics.findings_by_severity.items():
        series.append(
            _series(
                "sentinelqa.findings.count",
                value=count,
                timestamp=timestamp,
                tags=[*tags, f"severity:{severity}"],
                metric_type=2,  # 2 = count
            )
        )
    for module_name, duration_ms in metrics.module_durations_ms.items():
        series.append(
            _series(
                "sentinelqa.module.duration_ms",
                value=duration_ms,
                timestamp=timestamp,
                tags=[*tags, f"module:{module_name}"],
            )
        )

    return {"series": series}


class DatadogPusher:
    """Stateless Datadog Metrics V2 pusher."""

    def __init__(
        self,
        *,
        api_key: str,
        site: str = DATADOG_DEFAULT_SITE,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not api_key.strip():
            raise DatadogError("DataDog API key is empty.")
        self._api_key = api_key
        self._endpoint = f"https://api.{site}/api/v2/series"
        self._client = client or HttpClient(
            auth=AuthHeader.header("DD-API-KEY", api_key),
            retry=retry,
        )

    def push(self, metrics: RunMetrics) -> str:
        payload = build_datadog_payload(metrics)
        try:
            body = self._client.post_text(self._endpoint, payload)
        except IntegrationHttpError as exc:
            raise DatadogError(f"datadog push failed: {exc}") from exc
        return body.strip()


def main() -> int:  # pragma: no cover — CLI sugar
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="sentinelqa-datadog")
    parser.add_argument(
        "--api-key",
        default=os.environ.get(DATADOG_API_KEY_ENV, ""),
    )
    parser.add_argument("--site", default=DATADOG_DEFAULT_SITE)
    parser.add_argument("--run-dir", type=Path, required=True)
    ns = parser.parse_args()
    if not ns.api_key:
        return 2
    from integrations.metrics.builder import extract_run_metrics

    metrics = extract_run_metrics(ns.run_dir)
    pusher = DatadogPusher(api_key=ns.api_key, site=ns.site)
    try:
        body = pusher.push(metrics)
    except DatadogError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(body)
    return 0


__all__ = [
    "DATADOG_API_KEY_ENV",
    "DATADOG_DEFAULT_SITE",
    "DatadogError",
    "DatadogPusher",
    "build_datadog_payload",
]
