"""``ChaosModule`` (Phase 23, PRD §10.8, CLAUDE.md §9, §6).

Lifecycle (CLAUDE.md §9):

- ``validate_prerequisites`` — re-enforces :class:`SafetyPolicy` so the
  module fails closed if the orchestrator wasn't called through the
  CLI / SDK happy path (CLAUDE.md §6: chaos scenarios stay scoped to
  authorized targets).
- ``plan``                   — no Playwright specs to enumerate
  (events flow in via JSONL).
- ``execute``                — ingests JSONL chaos events from the
  configured / option-supplied path, groups them by scenario, and
  synthesizes a placeholder :class:`RunnerOutcome`.
- ``collect_evidence``       — writes ``chaos/<category>.json`` per
  category plus ``chaos/index.json``. Raw events are NOT re-copied
  here; the ingestion source remains the canonical event log.
- ``emit_findings``          — translates each bad
  :class:`ChaosEvent` via
  :func:`modules.chaos.findings.findings_from_results`.
- ``emit_metrics``           — counts per-category scenarios, events,
  and bad observations.
- ``summarize``              — overlays findings on the synthesized
  :class:`RunnerOutcome`; status is ``skipped`` if every requested
  category reported zero events.

Safety boundary (CLAUDE.md §6, §39):

- Defaults off in ``modules.chaos``. The CI ``nightly`` mode flips it
  on explicitly; ``fast`` / ``standard`` do not.
- Every CLI invocation honors the standard SafetyPolicy mode (no
  destructive scenarios escape "safe"). Session-claim manipulation is
  Playwright-side only: the TS helpers never re-sign real JWTs.
- The module never reads CLI flags named ``--aggressive`` /
  ``--bypass`` / ``--stealth``; the ``tests/security`` guard greps
  the package + CLI to keep that property.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, ClassVar

from engine.config.schema import RootConfig
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyDecision, SafetyPolicy
from engine.runner.results import EnvironmentContext, RunnerOutcome

from modules.chaos.findings import findings_from_results
from modules.chaos.ingestion import (
    ChaosIngestError,
    group_by_scenario,
    read_event_file,
    reports_by_category,
)
from modules.chaos.models import (
    CHAOS_RESULT_SCHEMA_VERSION,
    ChaosCategory,
    ChaosCategoryReport,
    ChaosRunOutcome,
    ChaosScenarioResult,
)
from modules.chaos.options import ChaosModuleOptions
from modules.chaos.scenarios import (
    CATALOG_BY_ID,
    DEFAULT_CATEGORIES,
    scenarios_for_category,
)


def _read_options(ctx: ModuleContext) -> ChaosModuleOptions:
    """Hydrate :class:`ChaosModuleOptions` from ``ctx.options``."""

    raw = ctx.options or {}

    def _csv(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, list | tuple):
            return tuple(str(v).strip() for v in value if str(v).strip())
        return ()

    events_raw = raw.get("events_path")
    events_path: Path | None
    if events_raw is None:
        events_path = None
    elif isinstance(events_raw, Path):
        events_path = events_raw
    else:
        events_path = Path(str(events_raw))

    return ChaosModuleOptions(
        enabled_categories=_csv(raw.get("enabled_categories")),
        enabled_scenarios=_csv(raw.get("enabled_scenarios")),
        flows=_csv(raw.get("flows")),
        events_path=events_path,
    )


def _resolve_categories(
    config: RootConfig, options: ChaosModuleOptions
) -> tuple[ChaosCategory, ...]:
    configured: tuple[ChaosCategory, ...] = tuple(config.chaos.enabled_categories)
    if options.enabled_categories:
        requested = set(options.enabled_categories)
        return tuple(c for c in configured if c in requested)
    return configured


def _resolve_scenarios(
    config: RootConfig, options: ChaosModuleOptions, categories: tuple[ChaosCategory, ...]
) -> tuple[str, ...]:
    catalog_ids = tuple(s.id for c in categories for s in scenarios_for_category(c))
    config_enabled = tuple(config.chaos.enabled_scenarios) or catalog_ids
    if options.enabled_scenarios:
        requested = set(options.enabled_scenarios)
        return tuple(s for s in config_enabled if s in requested)
    return tuple(s for s in config_enabled if s in catalog_ids)


def _filter_results_by_scenarios(
    results: tuple[ChaosScenarioResult, ...], allowed: tuple[str, ...]
) -> tuple[ChaosScenarioResult, ...]:
    if not allowed:
        return results
    allowed_set = set(allowed)
    return tuple(r for r in results if r.scenario_id in allowed_set)


def _filter_results_by_flows(
    results: tuple[ChaosScenarioResult, ...], flows: tuple[str, ...]
) -> tuple[ChaosScenarioResult, ...]:
    if not flows:
        return results
    flow_set = set(flows)
    return tuple(r for r in results if r.flow in flow_set)


def _default_events_path(ctx: ModuleContext) -> Path:
    return ctx.run_dir / "chaos" / "events.jsonl"


def _category_skip_report(category: ChaosCategory, reason: str) -> ChaosCategoryReport:
    return ChaosCategoryReport(
        category=category,
        results=(),
        duration_ms=0,
        skipped=True,
        skip_reason=reason,
    )


class ChaosModule(SentinelModule):
    """PRD §10.8 chaos / adversarial testing wired into the lifecycle."""

    name: ClassVar[str] = "chaos"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        super().__init__(config, safety_decision)
        self._last_outcome: ChaosRunOutcome | None = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        SafetyPolicy().enforce(ctx.target, self._safety.mode)

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        del specs
        outcome = self._run_audit(ctx)
        self._last_outcome = outcome
        return _synthetic_runner_outcome(ctx, outcome)

    def collect_evidence(self, ctx: ModuleContext, outcome: RunnerOutcome) -> tuple[Evidence, ...]:
        del outcome
        run_outcome = self._last_outcome
        if run_outcome is None:
            return ()
        chaos_dir = ctx.run_dir / "chaos"
        chaos_dir.mkdir(parents=True, exist_ok=True)
        for report in run_outcome.categories:
            path = chaos_dir / f"{report.category}.json"
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        index_path = chaos_dir / "index.json"
        index_path.write_text(
            json.dumps(run_outcome.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return ()

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        run_outcome = self._last_outcome
        if run_outcome is None:
            return ()
        artifact_paths: dict[str, str] = {
            report.category: f"chaos/{report.category}.json" for report in run_outcome.categories
        }
        results = tuple(result for report in run_outcome.categories for result in report.results)
        return findings_from_results(
            results=results,
            run_id=ctx.run_id,
            target_base_url=str(ctx.target.base_url),
            id_generator=ctx.id_generator,
            artifact_paths=artifact_paths,
        )

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        del ctx, outcome
        run_outcome = self._last_outcome
        if run_outcome is None:
            return {"categories": 0}
        total_results = sum(len(r.results) for r in run_outcome.categories)
        total_events = sum(
            len(result.events) for report in run_outcome.categories for result in report.results
        )
        bad_events = sum(
            len(result.bad_events) for report in run_outcome.categories for result in report.results
        )
        skipped_categories = sum(1 for r in run_outcome.categories if r.skipped)
        return {
            "categories": len(run_outcome.categories),
            "categories_skipped": skipped_categories,
            "scenarios_executed": total_results,
            "events_total": total_events,
            "events_bad": bad_events,
            "duration_ms": run_outcome.duration_ms,
            "incomplete": int(run_outcome.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        run_outcome = self._last_outcome
        if run_outcome is None or all(c.skipped for c in run_outcome.categories):
            status: ModuleStatus = "skipped"
        elif run_outcome.incomplete:
            status = "incomplete"
        elif any(f.severity in {"critical", "high"} for f in findings):
            status = "failed"
        else:
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

    def _run_audit(self, ctx: ModuleContext) -> ChaosRunOutcome:
        options = _read_options(ctx)
        categories = _resolve_categories(self._config, options)
        enabled_scenarios = _resolve_scenarios(self._config, options, categories)
        audit_log_path = ctx.run_dir / "audit.log"
        write_audit_entry(
            audit_log_path,
            {
                "event": "chaos.start",
                "run_id": ctx.run_id,
                "categories": list(categories),
                "scenarios": list(enabled_scenarios),
                "mode": self._safety.mode,
            },
        )
        started = perf_counter()

        events_path = options.events_path or _default_events_path(ctx)
        incomplete = False
        scenario_results: tuple[ChaosScenarioResult, ...] = ()
        if events_path.exists():
            try:
                events = read_event_file(events_path)
            except ChaosIngestError as exc:
                incomplete = True
                events = ()
                write_audit_entry(
                    audit_log_path,
                    {
                        "event": "chaos.ingest_error",
                        "path": str(events_path),
                        "reason": str(exc),
                    },
                )
            scenario_results = group_by_scenario(events)
            scenario_results = _filter_results_by_scenarios(scenario_results, enabled_scenarios)
            scenario_results = _filter_results_by_flows(scenario_results, options.flows)

        per_category = reports_by_category(scenario_results)
        present = {report.category for report in per_category}
        synthesized: list[ChaosCategoryReport] = list(per_category)
        for category in categories:
            if category not in present:
                synthesized.append(
                    _category_skip_report(
                        category,
                        (
                            "no chaos events produced for this category "
                            f"(expected events file at {events_path.name})."
                        ),
                    )
                )
        synthesized.sort(key=lambda r: ("network", "session", "ux", "data").index(r.category))

        elapsed_ms = int((perf_counter() - started) * 1000)
        events_path_str: str | None
        if events_path.exists():
            try:
                events_path_str = str(events_path.relative_to(ctx.run_dir))
            except ValueError:
                events_path_str = str(events_path)
        else:
            events_path_str = None
        outcome = ChaosRunOutcome(
            schema_version=CHAOS_RESULT_SCHEMA_VERSION,
            categories=tuple(synthesized),
            duration_ms=elapsed_ms,
            incomplete=incomplete,
            events_path=events_path_str,
        )
        write_audit_entry(
            audit_log_path,
            {
                "event": "chaos.complete",
                "run_id": ctx.run_id,
                "categories": [c.category for c in outcome.categories],
                "scenarios_executed": sum(len(r.results) for r in outcome.categories),
                "bad_events": sum(
                    len(result.bad_events)
                    for report in outcome.categories
                    for result in report.results
                ),
                "incomplete": outcome.incomplete,
            },
        )
        return outcome


def _synthetic_runner_outcome(ctx: ModuleContext, outcome: ChaosRunOutcome) -> RunnerOutcome:
    """Build a placeholder :class:`RunnerOutcome` so the base contract holds."""

    status: ModuleStatus
    if not outcome.categories or all(c.skipped for c in outcome.categories):
        status = "skipped"
    elif outcome.incomplete:
        status = "incomplete"
    else:
        status = "passed"
    return RunnerOutcome.build(
        module_name="chaos",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=outcome.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> ChaosModule:
    return ChaosModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    """Idempotently register :class:`ChaosModule` with the registry."""

    reg = registry or default_registry()
    if "chaos" in reg.modules:
        return
    reg.register_module("chaos", _factory)


# Re-export so callers can import the public surface from the package
# root without pulling submodules directly.
_ = (
    DEFAULT_CATEGORIES,
    CATALOG_BY_ID,
    datetime.now(UTC),  # ensure datetime import is not pruned
)


__all__ = [
    "ChaosModule",
    "ChaosModuleOptions",
    "register_with_default_registry",
]
