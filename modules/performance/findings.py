"""Translate performance evaluator violations into typed :class:`Finding` records.

CLAUDE §27 is load-bearing: every description begins with
"Synthetic performance check" so consumers cannot mistake the lab
measurement for Real-User Monitoring. The forbidden-phrase guard in
``tests/security/test_synthetic_perf_labeling.py`` keeps us honest.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.config.schema import PerformanceBudgets
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.performance.api_latency import (
    ApiLatencyViolation,
    evaluate_api_latency,
)
from modules.performance.bundle_cpu import (
    BundleSizeViolation,
    LongTaskViolation,
    evaluate_bundle_size,
    evaluate_long_tasks,
)
from modules.performance.models import PerformancePageResult
from modules.performance.nav_stability import (
    NavStabilityViolation,
    evaluate_nav_stability,
)
from modules.performance.page_budget import (
    PageBudgetViolation,
    evaluate_page_budgets,
)

_LABEL = "Synthetic performance check"
"""Required prefix on every performance finding (CLAUDE §27)."""


# Severity policy. Page-budget exceedances are graded by overage:
#   ≤ 50%  → medium
#   > 50%  → high
# CPU + bundle violations follow the same rule.
# API latency is medium by default (one slow endpoint rarely blocks
# release on its own) and escalates to high when overage > 100%.
# Nav-stability is always low (it is a heuristic — CLAUDE §27).
def _severity_for_overage(pct: float, *, threshold: float = 50.0) -> Severity:
    return "high" if pct > threshold else "medium"


def short_hash(*parts: str) -> str:
    payload = "|".join(parts)
    digest = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()
    return digest[:8]


def findings_from_page(
    *,
    page: PerformancePageResult,
    budgets: PerformanceBudgets,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None = None,
    margin_pct: float = 0.0,
    api_min_samples: int = 5,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Translate one :class:`PerformancePageResult` into a tuple of findings."""

    timestamp = now or datetime.now(UTC)
    out: list[Finding] = []

    out.extend(
        _page_budget_findings(
            violations=evaluate_page_budgets(page.page_metrics, budgets, margin_pct=margin_pct),
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    out.extend(
        _api_latency_findings(
            violations=evaluate_api_latency(
                page.api_endpoints,
                budgets,
                min_samples=api_min_samples,
                margin_pct=margin_pct,
            ),
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    bundle_violation = evaluate_bundle_size(page.bundle, budgets, margin_pct=margin_pct)
    if bundle_violation is not None:
        out.append(
            _bundle_size_finding(
                violation=bundle_violation,
                page=page,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_path,
                timestamp=timestamp,
            )
        )
    long_task_violation = evaluate_long_tasks(page.long_tasks, budgets, margin_pct=margin_pct)
    if long_task_violation is not None:
        out.append(
            _long_task_finding(
                violation=long_task_violation,
                page=page,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_path,
                timestamp=timestamp,
            )
        )
    out.extend(
        _nav_stability_findings(
            violations=evaluate_nav_stability(page.nav_stability, budgets),
            page=page,
            run_id=run_id,
            target_base_url=target_base_url,
            id_generator=id_generator,
            artifact_path=artifact_path,
            timestamp=timestamp,
        )
    )
    return tuple(out)


def findings_from_pages(
    *,
    pages: Iterable[PerformancePageResult],
    budgets: PerformanceBudgets,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_paths: dict[str, str] | None = None,
    margin_pct: float = 0.0,
    api_min_samples: int = 5,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    timestamp = now or datetime.now(UTC)
    artifact_paths = artifact_paths or {}
    out: list[Finding] = []
    for page in pages:
        out.extend(
            findings_from_page(
                page=page,
                budgets=budgets,
                run_id=run_id,
                target_base_url=target_base_url,
                id_generator=id_generator,
                artifact_path=artifact_paths.get(page.route),
                margin_pct=margin_pct,
                api_min_samples=api_min_samples,
                now=timestamp,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Per-check translators
# ---------------------------------------------------------------------------

_PAGE_METRIC_UNITS: dict[str, str] = {
    "lcp_ms": "ms",
    "ttfb_ms": "ms",
    "inp_ms": "ms",
    "cls": "",
}
_PAGE_METRIC_HUMAN: dict[str, str] = {
    "lcp_ms": "Largest Contentful Paint",
    "ttfb_ms": "Time to First Byte",
    "inp_ms": "Interaction to Next Paint",
    "cls": "Cumulative Layout Shift",
}


def _format_number(value: float, *, unit: str) -> str:
    if unit == "":
        return f"{value:.3f}"
    return f"{value:.0f}{unit}"


def _page_budget_findings(
    *,
    violations: tuple[PageBudgetViolation, ...],
    page: PerformancePageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for v in violations:
        unit = _PAGE_METRIC_UNITS.get(v.metric, "")
        human = _PAGE_METRIC_HUMAN.get(v.metric, v.metric)
        title = (
            f"{_LABEL}: {human} {_format_number(v.observed, unit=unit)} > "
            f"{_format_number(v.budget, unit=unit)} budget on route {page.route!r}"
        )
        description = (
            f"{_LABEL} measured a median {human} of "
            f"{_format_number(v.observed, unit=unit)} across {v.samples} synthetic "
            f"load(s) on route {page.route!r}, which exceeds the configured budget "
            f"of {_format_number(v.budget, unit=unit)} by {v.overage_pct:.1f}%. "
            "These are lab measurements (CLAUDE §27): they catch regressions "
            "reliably but do not represent Real-User Monitoring data."
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="performance",
                category=f"perf.page.{v.metric}",
                severity=_severity_for_overage(v.overage_pct),
                confidence=0.9,
                title=_truncate(title, 300),
                description=description,
                location=FindingLocation(route=page.route),
                evidence=_evidence(page, artifact_path, id_generator),
                reproduction_steps=(
                    f"Open {page.url} in a desktop Chromium browser.",
                    f"Record the {human} via PerformanceObserver across " f"{v.samples} reloads.",
                    "Compare the median against the configured budget.",
                ),
                affected_target=target_base_url,
                recommendation=_recommendation_for_metric(v.metric),
                suggested_fix=f"perf:page:{v.metric}:#{short_hash(page.route, v.metric)}",
                created_at=timestamp,
            )
        )
    return out


def _api_latency_findings(
    *,
    violations: tuple[ApiLatencyViolation, ...],
    page: PerformancePageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for v in violations:
        severity: Severity = "high" if v.overage_pct > 100.0 else "medium"
        title = (
            f"{_LABEL}: {v.method} {v.endpoint} P95 {v.observed_p95_ms:.0f}ms > "
            f"{v.budget_p95_ms}ms budget"
        )
        description = (
            f"{_LABEL} measured a P95 latency of {v.observed_p95_ms:.0f}ms "
            f"for {v.method} {v.endpoint!r} on route {page.route!r} across "
            f"{v.samples} synthetic call(s), exceeding the configured P95 "
            f"budget of {v.budget_p95_ms}ms by {v.overage_pct:.1f}%. "
            "These are lab measurements (CLAUDE §27): they catch regressions "
            "but do not represent Real-User Monitoring data."
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="performance",
                category="perf.api.p95",
                severity=severity,
                confidence=0.85,
                title=_truncate(title, 300),
                description=description,
                location=FindingLocation(route=page.route),
                evidence=_evidence(page, artifact_path, id_generator),
                reproduction_steps=(
                    f"Open {page.url} in a desktop Chromium browser.",
                    f"Trigger the request to {v.method} {v.endpoint!r}.",
                    "Record durations across repeated visits and compute the P95.",
                ),
                affected_target=target_base_url,
                recommendation=(
                    f"Profile {v.method} {v.endpoint!r}; reduce the P95 below "
                    f"{v.budget_p95_ms}ms (consider caching, parallelism, or "
                    "moving expensive work off the request path)."
                ),
                suggested_fix=(
                    f"perf:api:{v.method.lower()}:#{short_hash(page.route, v.method, v.endpoint)}"
                ),
                created_at=timestamp,
            )
        )
    return out


def _bundle_size_finding(
    *,
    violation: BundleSizeViolation,
    page: PerformancePageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> Finding:
    title = (
        f"{_LABEL}: JS bundle {violation.observed_kb:.0f}KB > "
        f"{violation.budget_kb}KB budget on route {page.route!r}"
    )
    description = (
        f"{_LABEL} transferred {violation.observed_kb:.0f}KB of JavaScript across "
        f"{violation.file_count} file(s) on route {page.route!r}, exceeding the "
        f"configured budget of {violation.budget_kb}KB by {violation.overage_pct:.1f}%. "
        "Transfer size is wire bytes (post-compression). These are lab "
        "measurements (CLAUDE §27): the budget is a release-confidence proxy, "
        "not a real-user telemetry reading."
    )
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module="performance",
        category="perf.bundle.size",
        severity=_severity_for_overage(violation.overage_pct),
        confidence=0.95,
        title=_truncate(title, 300),
        description=description,
        location=FindingLocation(route=page.route),
        evidence=_evidence(page, artifact_path, id_generator),
        reproduction_steps=(
            f"Open {page.url} with a clean cache in a Chromium browser.",
            "Sum the transferred bytes of every response with content-type "
            "application/javascript in the Network panel.",
            f"Compare the total against the {violation.budget_kb}KB budget.",
        ),
        affected_target=target_base_url,
        recommendation=(
            "Identify the largest bundles (code-split routes, vendor chunks, "
            "polyfills), enable tree-shaking, defer non-critical scripts, and "
            "consider serving differential bundles for modern browsers."
        ),
        suggested_fix=f"perf:bundle:#{short_hash(page.route, 'bundle')}",
        created_at=timestamp,
    )


def _long_task_finding(
    *,
    violation: LongTaskViolation,
    page: PerformancePageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> Finding:
    title = (
        f"{_LABEL}: CPU blocking {violation.total_blocking_ms:.0f}ms > "
        f"{violation.budget_ms}ms budget on route {page.route!r}"
    )
    description = (
        f"{_LABEL} observed {violation.count} long task(s) totalling "
        f"{violation.total_blocking_ms:.0f}ms of main-thread blocking on "
        f"route {page.route!r} (longest single task: {violation.longest_ms:.0f}ms), "
        f"exceeding the configured budget of {violation.budget_ms}ms by "
        f"{violation.overage_pct:.1f}%. These are lab measurements "
        "(CLAUDE §27): a blocked headless main thread is a real signal but "
        "not the same as a blocked main thread on a constrained user device."
    )
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module="performance",
        category="perf.cpu.long_tasks",
        severity=_severity_for_overage(violation.overage_pct),
        confidence=0.85,
        title=_truncate(title, 300),
        description=description,
        location=FindingLocation(route=page.route),
        evidence=_evidence(page, artifact_path, id_generator),
        reproduction_steps=(
            f"Open {page.url} with Performance recording active in a Chromium " "browser.",
            "Look for tasks longer than 50ms on the main thread.",
            "Sum the blocking time and compare against the long-task budget.",
        ),
        affected_target=target_base_url,
        recommendation=(
            "Break long tasks into smaller chunks (yield via "
            "scheduler.postTask, requestIdleCallback, or setTimeout); move "
            "heavy work off the main thread via web workers."
        ),
        suggested_fix=f"perf:cpu:#{short_hash(page.route, 'longtask')}",
        created_at=timestamp,
    )


def _nav_stability_findings(
    *,
    violations: tuple[NavStabilityViolation, ...],
    page: PerformancePageResult,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_path: str | None,
    timestamp: datetime,
) -> list[Finding]:
    out: list[Finding] = []
    for v in violations:
        if v.metric == "dom":
            title = (
                f"{_LABEL}: potential memory leak — DOM nodes grew "
                f"{v.observed_pct:.1f}% across {v.samples} visits to {page.route!r}"
            )
        else:
            title = (
                f"{_LABEL}: potential memory leak — JS heap grew "
                f"{v.observed_pct:.1f}% across {v.samples} visits to {page.route!r}"
            )
        description = (
            f"{_LABEL} observed {v.metric.upper() if v.metric == 'dom' else 'JS heap'} "
            f"growth of {v.observed_pct:.1f}% across {v.samples} synthetic visits "
            f"to route {page.route!r}, exceeding the configured tolerance of "
            f"{v.threshold_pct:.1f}%. This is a heuristic (CLAUDE §27) — small "
            "growth is normal as caches warm; investigate dangling listeners, "
            "detached DOM trees, or unbounded in-memory state."
        )
        out.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="performance",
                category=f"perf.nav.{v.metric}_growth",
                severity="low",
                # Heuristic — keep confidence well below 1.0 so Phase 14
                # does not over-block on this signal.
                confidence=0.5,
                title=_truncate(title, 300),
                description=description,
                location=FindingLocation(route=page.route),
                evidence=_evidence(page, artifact_path, id_generator),
                reproduction_steps=(
                    f"Open {page.url}.",
                    f"Repeatedly navigate to the same route {v.samples} times.",
                    "Watch the DOM node count and JS heap in DevTools " "between visits.",
                ),
                affected_target=target_base_url,
                recommendation=(
                    "Audit components that mount on the route for listeners "
                    "removed in cleanup hooks; check for unbounded caches; "
                    "use the heap snapshot diff to find retained references."
                ),
                suggested_fix=f"perf:nav:{v.metric}:#{short_hash(page.route, v.metric)}",
                created_at=timestamp,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _evidence(
    page: PerformancePageResult,
    artifact_path: str | None,
    id_generator: IdGenerator,
) -> tuple[Evidence, ...]:
    if artifact_path:
        return (
            Evidence(
                id=id_generator.new("EVD"),
                type="source_ref",
                path=Path(artifact_path),
            ),
        )
    return (
        Evidence(
            id=id_generator.new("EVD"),
            type="console_log",
            path=Path("logs/runner.performance.log"),
        ),
    )


_RECOMMENDATIONS: dict[str, str] = {
    "lcp_ms": (
        "Inline above-the-fold CSS, preload the hero image / font, defer "
        "non-critical JS, and reduce server response time."
    ),
    "ttfb_ms": (
        "Reduce server processing time, enable HTTP caching, move work off "
        "the request path, and use a CDN."
    ),
    "inp_ms": (
        "Break long tasks, avoid synchronous storage access during input, "
        "and debounce expensive handlers."
    ),
    "cls": (
        "Reserve space for images and ads with width/height attributes, "
        "avoid injecting content above existing content, and pre-size "
        "embeds."
    ),
}


def _recommendation_for_metric(metric: str) -> str:
    return _RECOMMENDATIONS.get(
        metric,
        "Profile the route in Chrome DevTools and reduce work attributed " "to this metric.",
    )


__all__ = [
    "findings_from_page",
    "findings_from_pages",
    "short_hash",
]
