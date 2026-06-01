"""``PerformanceModule`` (, the documentation, ADR-0017).

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — no-op; the sentinel-ts probe lives in
 ``execute`` so projects without an installed runtime still report
 ``skipped`` instead of ``errored``.
- ``plan`` — resolves the route list (CLI options
 → discovery.json → config.performance.routes → ``("/",)`` only when
 the CLI explicitly injects it).
- ``execute`` — calls the configured :class:`PerformanceRunner`
 (production: :class:`LocalPerformanceRunner`).
- ``collect_evidence`` — pass-through; the runner already wrote
 one ``<run-dir>/perf/<route-slug>.json`` per page.
- ``emit_findings`` — translates each :class:`PerformancePageResult`
 via :func:`modules.performance.findings.findings_from_pages`.
- ``emit_metrics`` — counts violations, samples, and totals.
- ``summarize`` — overlays findings on a synthesized
 :class:`ModuleResult` (no Playwright tests run; no
 :class:`RunnerOutcome` exists).

CLAUDE §27 is the load-bearing rule: every finding's description begins
with "Synthetic performance check"; the forbidden-phrase guard in
``tests/security/test_synthetic_perf_labeling.py`` enforces this.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from engine.config.schema import RootConfig
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from engine.runner.results import EnvironmentContext, RunnerOutcome

from modules.performance.findings import findings_from_pages
from modules.performance.models import (
    PerformanceRunOutcome,
)
from modules.performance.options import PerformanceModuleOptions
from modules.performance.runner import (
    LocalPerformanceRunner,
    PerformanceInvocation,
    PerformanceRunner,
)

PerformanceRunnerFactory = Callable[[RootConfig, SafetyDecision], PerformanceRunner]


class PerformanceModule(SentinelModule):
    """the documentation performance checks wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "performance"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
        *,
        runner_factory: PerformanceRunnerFactory | None = None,
    ) -> None:
        super().__init__(config, safety_decision)
        self._uses_default_factory = runner_factory is None
        self._runner_factory: PerformanceRunnerFactory = runner_factory or _default_runner_factory

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        return

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        # SentinelModule.plan returns spec paths; the performance module
        # works in routes, not specs. The base contract is satisfied with
        # an empty tuple — the real plan is resolved in execute.
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        del specs
        outcome = self._run_audit(ctx)
        self._last_outcome = outcome
        return _synthetic_runner_outcome(ctx, outcome)

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        perf_outcome = getattr(self, "_last_outcome", None)
        if perf_outcome is None:
            return ()
        artifact_paths = {
            page.route: f"perf/{_route_slug(page.route)}.json" for page in perf_outcome.pages
        }
        return findings_from_pages(
            pages=perf_outcome.pages,
            budgets=self._config.performance.budgets,
            run_id=ctx.run_id,
            target_base_url=str(ctx.target.base_url),
            id_generator=ctx.id_generator,
            artifact_paths=artifact_paths,
            api_min_samples=self._config.performance.api_min_samples_for_p95,
        )

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        del ctx, outcome
        perf_outcome = getattr(self, "_last_outcome", None)
        if perf_outcome is None:
            return {"pages": 0}
        api_calls = sum(len(p.api_samples) for p in perf_outcome.pages)
        endpoints = sum(len(p.api_endpoints) for p in perf_outcome.pages)
        long_tasks = sum(p.long_tasks.count for p in perf_outcome.pages)
        bundle_total = sum(p.bundle.transfer_total_kb for p in perf_outcome.pages)
        return {
            "pages": len(perf_outcome.pages),
            "api_samples": api_calls,
            "api_endpoints": endpoints,
            "long_tasks": long_tasks,
            "bundle_transfer_kb_total": float(round(bundle_total, 2)),
            "duration_ms": perf_outcome.duration_ms,
            "incomplete": int(perf_outcome.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        perf_outcome = getattr(self, "_last_outcome", None)
        if perf_outcome is None or not perf_outcome.pages:
            status: ModuleStatus = "skipped"
        elif perf_outcome.incomplete:
            status = "incomplete"
        elif any(f.severity in {"critical", "high"} for f in findings):
            status = "failed"
        else:
            # medium/low findings don't block this module's status — the
            # Phase-14 quality score is what ultimately gates release.
            status = "passed"
        merged_metrics = dict(outcome.module_result.metrics)
        merged_metrics.update(metrics)
        return outcome.module_result.model_copy(
            update={
                "findings": tuple(findings),
                "metrics": merged_metrics,
                "status": status,
            }
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_audit(self, ctx: ModuleContext) -> PerformanceRunOutcome:
        options = _read_options(ctx)
        routes = _resolve_routes(self._config, options)
        if not routes:
            return PerformanceRunOutcome(pages=(), incomplete=False, duration_ms=0)

        perf_cfg = self._config.performance
        samples = options.samples if options.samples is not None else perf_cfg.samples
        repeated_nav = (
            options.repeated_nav_samples
            if options.repeated_nav_samples is not None
            else perf_cfg.repeated_nav_samples
        )
        invocation = PerformanceInvocation(
            run_id=ctx.run_id,
            run_dir=ctx.run_dir,
            target=str(ctx.target.base_url),
            routes=tuple(routes),
            samples=samples,
            repeated_nav_samples=repeated_nav,
            request_timeout_seconds=perf_cfg.request_timeout_seconds,
            api_path_allowlist=tuple(perf_cfg.api_path_allowlist),
        )
        runner = self._runner_factory(self._config, self._safety)
        return runner.run(invocation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> PerformanceModuleOptions:
    raw = ctx.options.get("performance") if "performance" in ctx.options else ctx.options
    if isinstance(raw, PerformanceModuleOptions):
        return raw
    if isinstance(raw, dict):
        routes_value: Any = raw.get("routes") or ()
        if isinstance(routes_value, str):
            routes_tuple: tuple[str, ...] = (routes_value,)
        else:
            routes_tuple = tuple(str(r) for r in routes_value)
        discovery_value: Any = raw.get("discovery_path")
        discovery_path: Path | None
        if discovery_value is None:
            discovery_path = None
        elif isinstance(discovery_value, Path):
            discovery_path = discovery_value
        else:
            discovery_path = Path(str(discovery_value))
        samples_value = raw.get("samples")
        nav_value = raw.get("repeated_nav_samples")
        return PerformanceModuleOptions(
            routes=routes_tuple,
            discovery_path=discovery_path,
            samples=int(samples_value) if samples_value is not None else None,
            repeated_nav_samples=int(nav_value) if nav_value is not None else None,
            extra_env=raw.get("extra_env", {}),
        )
    return PerformanceModuleOptions()


def _resolve_routes(
    config: RootConfig,
    options: PerformanceModuleOptions,
) -> tuple[str, ...]:
    """Resolve the route set in priority order: CLI → discovery → config → empty."""

    if options.routes:
        return tuple(_normalize_route(r) for r in options.routes)
    if options.discovery_path is not None:
        routes = _routes_from_discovery(options.discovery_path)
        if routes:
            return routes
    if config.performance.routes:
        return tuple(_normalize_route(r) for r in config.performance.routes)
    # When no caller has told us which routes to audit, the module
    # short-circuits — `sentinel audit` skips the module silently;
    # `sentinel perf` injects the ("/",) fallback explicitly.
    return ()


def _routes_from_discovery(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates: list[str] = []
    raw_routes = payload.get("routes") if isinstance(payload, dict) else None
    if isinstance(raw_routes, list):
        for entry in raw_routes:
            if isinstance(entry, dict):
                value = entry.get("path") or entry.get("route")
                if isinstance(value, str) and value:
                    candidates.append(value)
            elif isinstance(entry, str):
                candidates.append(entry)
    seen: set[str] = set()
    ordered: list[str] = []
    for route in candidates:
        normalized = _normalize_route(route)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _normalize_route(route: str) -> str:
    cleaned = route.strip()
    if not cleaned:
        return "/"
    if cleaned.startswith("/"):
        return cleaned
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return "/" + cleaned


def _route_slug(route: str) -> str:
    """Filesystem-safe slug for a route (matches the TS subcommand)."""

    if route in {"", "/"}:
        return "root"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", route).strip("-")
    return base or "root"


def _synthetic_runner_outcome(
    ctx: ModuleContext, perf_outcome: PerformanceRunOutcome
) -> RunnerOutcome:
    """Build a placeholder :class:`RunnerOutcome` so the base contract holds."""

    status: ModuleStatus = (
        "skipped"
        if not perf_outcome.pages
        else ("incomplete" if perf_outcome.incomplete else "passed")
    )
    return RunnerOutcome.build(
        module_name="performance",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=perf_outcome.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _default_runner_factory(
    config: RootConfig,
    safety_decision: SafetyDecision,
) -> PerformanceRunner:
    return LocalPerformanceRunner(config=config, safety=safety_decision)


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> PerformanceModule:
    return PerformanceModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "performance" in reg.modules:
        return
    reg.register_module("performance", _factory)


_ = datetime.now(UTC)  # keep zoneinfo import live for ruff/mypy


__all__ = [
    "PerformanceModule",
    "PerformanceModuleOptions",
    "PerformanceRunnerFactory",
    "_factory",
    "register_with_default_registry",
]
