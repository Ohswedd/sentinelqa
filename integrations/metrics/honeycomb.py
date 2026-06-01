# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Honeycomb Events API push adapter."""

from __future__ import annotations

import logging
import os
from typing import Any, Final

from integrations._http import AuthHeader, HttpClient, IntegrationHttpError, RetrySpec
from integrations.metrics.builder import RunMetrics

HONEYCOMB_API_KEY_ENV: Final[str] = "SENTINELQA_HONEYCOMB_API_KEY"
HONEYCOMB_API_BASE: Final[str] = "https://api.honeycomb.io/1/events"
DEFAULT_DATASET: Final[str] = "sentinelqa"

logger = logging.getLogger("sentinelqa.integrations.honeycomb")


class HoneycombError(RuntimeError):
    """Raised when a Honeycomb push cannot complete safely."""


def build_honeycomb_event(metrics: RunMetrics) -> dict[str, Any]:
    """Honeycomb takes a single flat JSON object per event."""

    event: dict[str, Any] = {
        "service.name": "sentinelqa",
        "sentinelqa.run_id": metrics.run_id,
        "sentinelqa.status": metrics.status,
        "sentinelqa.target_host": metrics.target_host,
        "sentinelqa.duration_ms": metrics.duration_ms,
    }
    if metrics.quality_score is not None:
        event["sentinelqa.quality_score"] = metrics.quality_score
    for severity, count in metrics.findings_by_severity.items():
        event[f"sentinelqa.findings.{severity}"] = count
    for module_name, duration_ms in metrics.module_durations_ms.items():
        event[f"sentinelqa.module.{module_name}.duration_ms"] = duration_ms
    return event


class HoneycombPusher:
    """Stateless Honeycomb events pusher."""

    def __init__(
        self,
        *,
        api_key: str,
        dataset: str = DEFAULT_DATASET,
        endpoint_base: str = HONEYCOMB_API_BASE,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
    ) -> None:
        if not api_key.strip():
            raise HoneycombError("Honeycomb API key is empty.")
        if not dataset.strip():
            raise HoneycombError("Honeycomb dataset is empty.")
        self._api_key = api_key
        self._endpoint = f"{endpoint_base.rstrip('/')}/{dataset}"
        self._client = client or HttpClient(
            auth=AuthHeader.header("X-Honeycomb-Team", api_key),
            retry=retry,
        )

    def push(self, metrics: RunMetrics) -> str:
        event = build_honeycomb_event(metrics)
        try:
            body = self._client.post_text(self._endpoint, event)
        except IntegrationHttpError as exc:
            raise HoneycombError(f"honeycomb push failed: {exc}") from exc
        return body.strip()


def main() -> int:  # pragma: no cover — CLI sugar
    import argparse
    import json as _json
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="sentinelqa-honeycomb")
    parser.add_argument("--api-key", default=os.environ.get(HONEYCOMB_API_KEY_ENV, ""))
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--run-dir", type=Path, required=True)
    ns = parser.parse_args()
    if not ns.api_key:
        return 2
    from integrations.metrics.builder import extract_run_metrics

    metrics = extract_run_metrics(ns.run_dir)
    pusher = HoneycombPusher(api_key=ns.api_key, dataset=ns.dataset)
    try:
        body = pusher.push(metrics)
    except HoneycombError as exc:
        print(_json.dumps({"error": str(exc)}))
        return 1
    print(body)
    return 0


__all__ = [
    "HONEYCOMB_API_BASE",
    "HONEYCOMB_API_KEY_ENV",
    "HoneycombError",
    "HoneycombPusher",
    "build_honeycomb_event",
]
