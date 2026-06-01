# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""PagerDuty Events API V2 client.

Posts a single ``{event_action: trigger | resolve}`` event with the
SentinelQA run id as the ``dedup_key``. A second run with the same
id resolves the incident automatically; a third with a different
score re-triggers it.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from integrations._http import (
    HttpClient,
    IntegrationHttpError,
    RetrySpec,
)

PAGERDUTY_EVENTS_URL: Final[str] = "https://events.pagerduty.com/v2/enqueue"
PAGERDUTY_ROUTING_KEY_ENV: Final[str] = "SENTINELQA_PAGERDUTY_ROUTING_KEY"

logger = logging.getLogger("sentinelqa.integrations.pagerduty")

Severity = Literal["critical", "error", "warning", "info"]


class PagerDutyError(RuntimeError):
    """Raised when a PagerDuty post cannot complete safely."""


@dataclass(frozen=True, slots=True)
class PagerDutyTriggerRequest:
    """Inputs for one Events API enqueue."""

    routing_key: str
    run_id: str
    quality_score: float | None
    threshold: float
    base_url: str
    status: str
    findings_summary: dict[str, int] = field(default_factory=dict)
    report_url: str | None = None


@dataclass(frozen=True, slots=True)
class PagerDutyTriggerResult:
    """Outcome of one enqueue call."""

    event_action: Literal["trigger", "resolve", "skip"]
    dedup_key: str
    status_code: int = 0
    detail: str = ""


def should_trigger(*, quality_score: float | None, threshold: float) -> bool:
    """Return True iff the score breaches the threshold.

    Missing scores never trigger — the absence of a score means the
    run didn't reach the scoring stage and PagerDuty is the wrong
    surface for that. The reporter / mailer covers it.
    """

    if quality_score is None:
        return False
    return quality_score < threshold


_SEVERITY_FOR_GAP: Final[list[tuple[float, Severity]]] = [
    (30.0, "critical"),
    (15.0, "error"),
    (5.0, "warning"),
]


def _severity_from_gap(gap: float) -> Severity:
    for floor, severity in _SEVERITY_FOR_GAP:
        if gap >= floor:
            return severity
    return "info"


def build_trigger_payload(request: PagerDutyTriggerRequest) -> dict[str, Any]:
    """Build the Events V2 ``trigger`` payload."""

    score = request.quality_score if request.quality_score is not None else 0.0
    gap = max(request.threshold - score, 0.0)
    severity = _severity_from_gap(gap)
    summary = (
        f"SentinelQA quality score {score:.1f} is below threshold "
        f"{request.threshold:.1f} for {request.base_url}"
    )
    payload: dict[str, Any] = {
        "routing_key": request.routing_key,
        "event_action": "trigger",
        "dedup_key": _dedup_key(request),
        "payload": {
            "summary": summary,
            "source": request.base_url or "sentinelqa",
            "severity": severity,
            "component": "sentinelqa",
            "custom_details": {
                "run_id": request.run_id,
                "status": request.status,
                "quality_score": score,
                "threshold": request.threshold,
                "findings": request.findings_summary,
            },
        },
    }
    if request.report_url:
        payload["links"] = [{"href": request.report_url, "text": "SentinelQA report"}]
    return payload


def build_resolve_payload(request: PagerDutyTriggerRequest) -> dict[str, Any]:
    """Build the Events V2 ``resolve`` payload (closes a prior trigger)."""

    return {
        "routing_key": request.routing_key,
        "event_action": "resolve",
        "dedup_key": _dedup_key(request),
    }


def _dedup_key(request: PagerDutyTriggerRequest) -> str:
    """Group all PagerDuty events for the same target host."""

    return f"sentinelqa:{request.base_url or 'default'}"


class PagerDutyTrigger:
    """Stateless PagerDuty Events V2 client."""

    def __init__(
        self,
        *,
        client: HttpClient | None = None,
        retry: RetrySpec | None = None,
        endpoint: str = PAGERDUTY_EVENTS_URL,
    ) -> None:
        self._endpoint = endpoint
        self._client = client or HttpClient(retry=retry)

    def enqueue(self, request: PagerDutyTriggerRequest) -> PagerDutyTriggerResult:
        """Trigger or skip based on the score vs threshold."""

        if not should_trigger(
            quality_score=request.quality_score,
            threshold=request.threshold,
        ):
            return PagerDutyTriggerResult(
                event_action="skip",
                dedup_key=_dedup_key(request),
                detail="score above threshold; no incident enqueued",
            )
        payload = build_trigger_payload(request)
        return self._enqueue(payload, "trigger")

    def resolve(self, request: PagerDutyTriggerRequest) -> PagerDutyTriggerResult:
        """Force-resolve the dedup-key (for ``--resolve`` runs)."""

        return self._enqueue(build_resolve_payload(request), "resolve")

    def _enqueue(
        self,
        payload: Mapping[str, Any],
        action: Literal["trigger", "resolve"],
    ) -> PagerDutyTriggerResult:
        try:
            body = self._client.post_text(self._endpoint, payload)
        except IntegrationHttpError as exc:
            raise PagerDutyError(f"pagerduty {action} failed: {exc}") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {}
        return PagerDutyTriggerResult(
            event_action=action,
            dedup_key=str(payload.get("dedup_key", "")),
            status_code=200,
            detail=str(parsed.get("message", "")) or "ok",
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sentinelqa-pagerduty",
        description="Page on-call when a SentinelQA run's score drops below threshold.",
    )
    parser.add_argument(
        "--routing-key",
        default=os.environ.get(PAGERDUTY_ROUTING_KEY_ENV, ""),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--quality-score", type=float, default=None)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--status", default="")
    parser.add_argument("--report-url", default=None)
    parser.add_argument("--resolve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_arg_parser().parse_args(argv)
    if not ns.routing_key:
        sys.stderr.write(
            f"sentinelqa-pagerduty: --routing-key or {PAGERDUTY_ROUTING_KEY_ENV} required.\n"
        )
        return 2
    request = PagerDutyTriggerRequest(
        routing_key=ns.routing_key,
        run_id=ns.run_id,
        quality_score=ns.quality_score,
        threshold=ns.threshold,
        base_url=ns.base_url,
        status=ns.status,
        report_url=ns.report_url,
    )
    trigger = PagerDutyTrigger()
    try:
        result = trigger.resolve(request) if ns.resolve else trigger.enqueue(request)
    except PagerDutyError as exc:
        sys.stderr.write(f"sentinelqa-pagerduty: {exc}\n")
        return 1
    sys.stdout.write(
        json.dumps(
            {
                "event_action": result.event_action,
                "dedup_key": result.dedup_key,
                "detail": result.detail,
            }
        )
        + "\n"
    )
    return 0


__all__ = [
    "PAGERDUTY_EVENTS_URL",
    "PAGERDUTY_ROUTING_KEY_ENV",
    "PagerDutyError",
    "PagerDutyTrigger",
    "PagerDutyTriggerRequest",
    "PagerDutyTriggerResult",
    "build_resolve_payload",
    "build_trigger_payload",
    "main",
    "should_trigger",
]
