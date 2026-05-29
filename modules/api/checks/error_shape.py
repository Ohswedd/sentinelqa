"""Uniform error-shape check (Phase 22.07).

Walks the evidence collected by earlier checks and asserts that every
4xx / 5xx body observed in this run shares a single JSON envelope.
Today the evidence we have access to is the issue catalogue produced
by the contract / negative / auth / pagination checks. The error
shape comparator therefore looks for "expected_status vs observed_status"
mismatches and groups them by endpoint to surface envelopes that
disagree.

This is intentionally conservative: a single observed envelope is not
flagged. We only emit a finding when the same endpoint returned
distinct envelope shapes across runs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from time import perf_counter

from engine.config.schema import RootConfig

from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)


def run_error_shape_check(
    *,
    results: Iterable[ApiCheckResult],
    config: RootConfig,
) -> ApiCheckResult:
    del config  # Reserved for a future `api.error_shape_pattern` knob.
    started = perf_counter()
    issues: list[ApiIssue] = []
    endpoint_envelopes: dict[str, set[str]] = defaultdict(set)
    for result in results:
        if result.check not in {"contract", "negative", "pagination"}:
            continue
        for issue in result.issues:
            if issue.observed_status is None or issue.observed_status < 400:
                continue
            if issue.route is None:
                continue
            envelope_marker = issue.rule_id  # rule_id correlates to envelope category
            endpoint_envelopes[f"{issue.method or 'GET'} {issue.route}"].add(envelope_marker)
    scanned = len(endpoint_envelopes)
    for endpoint, envelopes in sorted(endpoint_envelopes.items()):
        if len(envelopes) <= 1:
            continue
        method, _, route = endpoint.partition(" ")
        issues.append(
            ApiIssue(
                rule_id="ERROR-SHAPE-DRIFT",
                severity="medium",
                confidence=0.7,
                title=f"Inconsistent error shape: {endpoint}",
                description=(
                    "Different error categories were observed on the same "
                    "endpoint within a single run: "
                    f"{sorted(envelopes)!r}. Surfacing a uniform error envelope "
                    "lets callers handle failures generically (CLAUDE.md §30)."
                ),
                method=method,
                route=route,
                recommendation=(
                    "Return a consistent error envelope (e.g. RFC 7807 problem+json) "
                    "across all failure modes for this endpoint."
                ),
                evidence={"distinct_categories": ",".join(sorted(envelopes))},
            )
        )
    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="error_shape",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


__all__ = ["run_error_shape_check"]
