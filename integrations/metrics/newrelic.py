# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""New Relic Metric API push adapter."""

from __future__ import annotations

import logging
import os
from typing import Any, Final

from integrations._http import AuthHeader, HttpClient, IntegrationHttpError, RetrySpec
from integrations.metrics.builder import RunMetrics

NEWRELIC_LICENSE_KEY_ENV: Final[str] = "SENTINELQA_NEWRELIC_LICENSE_KEY"
NEWRELIC_DEFAULT_ENDPOINT: Final[str] = "https://metric-api.newrelic.com/metric/v1"

logger = logging.getLogger("sentinelqa.integrations.newrelic")


class NewRelicError(RuntimeError):
    """Raised when a New Relic push cannot complete safely."""


def _metric(
    name: str,
    *,
    value: float,
    timestamp_ms: int,
    attributes: dict[str, Any],
    metric_type: str = "gauge",
) -> dict[str, Any]:
    return {
        "name": name,
        "type": metric_type,
        "value": value,
        "timestamp": timestamp_ms,
        "attributes": attributes,
    }


def _timestamp_ms(iso: str) -> int:
    from datetime import datetime

    try:
        return int(datetime.fromisoformat(iso).timestamp() * 1000)
    except ValueError:
        return 0


def build_newrelic_payload(metrics: RunMetrics) -> list[dict[str, Any]]:
    """Build the Metric API payload (a singleton list of one batch)."""

    timestamp_ms = _timestamp_ms(metrics.started_at) or 0
    attributes_base: dict[str, Any] = {
        "service": "sentinelqa",
        "run_id": metrics.run_id,
        "status": metrics.status,
    }
    if metrics.target_host:
        attributes_base["target_host"] = metrics.target_host

    metrics_list: list[dict[str, Any]] = []
    if metrics.quality_score is not None:
        metrics_list.append(
            _metric(
                "sentinelqa.quality_score",
                value=metrics.quality_score,
                timestamp_ms=timestamp_ms,
                attributes=attributes_base,
            )
        )
    metrics_list.append(
        _metric(
            "sentinelqa.duration_ms",
            value=metrics.duration_ms,
            timestamp_ms=timestamp_ms,
            attributes=attributes_base,
        )
    )
    for severity, count in metrics.findings_by_severity.items():
        metrics_list.append(
            _metric(
                "sentinelqa.findings.count",
                value=count,
                timestamp_ms=timestamp_ms,
                attributes={**attributes_base, "severity": severity},
                metric_type="count",
            )
        )
    for module_name, duration_ms in metrics.module_durations_ms.items():
        metrics_list.append(
            _metric(
                "sentinelqa.module.duration_ms",
                value=duration_ms,
                timestamp_ms=timestamp_ms,
                attributes={**attributes_base, "module": module_name},
            )
        )

    return [{"common": {"attributes": attributes_base}, "metrics": metrics_list}]


class NewRelicPusher:
    """Stateless New Relic Metric API pusher."""

    def __init__(
        self,
        *,
        license_key: str,
        endpoint: str = NEWRELIC_DEFAULT_ENDPOINT,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not license_key.strip():
            raise NewRelicError("New Relic license key is empty.")
        self._license_key = license_key
        self._endpoint = endpoint
        self._client = client or HttpClient(
            auth=AuthHeader.header("Api-Key", license_key),
            retry=retry,
        )

    def push(self, metrics: RunMetrics) -> str:
        # New Relic's Metric API expects an array of batches. Our
        # HttpClient only types Mapping[str, Any], but its underlying
        # json.dumps tolerates lists; cast to keep mypy quiet.
        payload = build_newrelic_payload(metrics)
        try:
            body = self._client.post_text(self._endpoint, payload)  # type: ignore[arg-type]
        except IntegrationHttpError as exc:
            raise NewRelicError(f"newrelic push failed: {exc}") from exc
        return body.strip()


def main() -> int:  # pragma: no cover — CLI sugar
    import argparse
    import json as _json
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="sentinelqa-newrelic")
    parser.add_argument(
        "--license-key",
        default=os.environ.get(NEWRELIC_LICENSE_KEY_ENV, ""),
    )
    parser.add_argument("--endpoint", default=NEWRELIC_DEFAULT_ENDPOINT)
    parser.add_argument("--run-dir", type=Path, required=True)
    ns = parser.parse_args()
    if not ns.license_key:
        return 2
    from integrations.metrics.builder import extract_run_metrics

    metrics = extract_run_metrics(ns.run_dir)
    pusher = NewRelicPusher(license_key=ns.license_key, endpoint=ns.endpoint)
    try:
        body = pusher.push(metrics)
    except NewRelicError as exc:
        print(_json.dumps({"error": str(exc)}))
        return 1
    print(body)
    return 0


__all__ = [
    "NEWRELIC_DEFAULT_ENDPOINT",
    "NEWRELIC_LICENSE_KEY_ENV",
    "NewRelicError",
    "NewRelicPusher",
    "build_newrelic_payload",
]
