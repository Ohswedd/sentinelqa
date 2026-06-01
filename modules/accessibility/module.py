"""``AccessibilityModule`` (, the documentation, ADR-0016).

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — no-op; the sentinel-ts probe lives in
 ``execute`` so projects without an installed runtime still report
 ``skipped`` instead of ``errored``.
- ``plan`` — resolves the route list (CLI options
 → discovery.json → config.accessibility.routes → ``("/",)`` default).
- ``execute`` — calls the configured :class:`A11yRunner`
 (production: :class:`LocalA11yRunner`).
- ``collect_evidence`` — pass-through; the runner already wrote
 one ``<run-dir>/a11y/<route-slug>.json`` per page.
- ``emit_findings`` — translates each :class:`A11yPageResult`
 via :func:`modules.accessibility.findings.findings_from_pages`.
- ``emit_metrics`` — counts violations + issues per check.
- ``summarize`` — overlays findings on a synthesized
 :class:`ModuleResult` (no Playwright tests run; no
 :class:`RunnerOutcome` exists).

CLAUDE §28 is enforced everywhere: descriptions begin with "Automated
accessibility check found" and full-compliance claims never appear.
The forbidden-phrase guard in
``tests/security/test_no_wcag_compliance_claims.py`` greps the module
package and the TS helper package for the exact strings to keep us
honest.
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

from modules.accessibility.findings import findings_from_pages
from modules.accessibility.models import (
    A11yRunOutcome,
)
from modules.accessibility.options import AccessibilityModuleOptions
from modules.accessibility.runner import (
    A11yInvocation,
    A11yRunner,
    A11yRunnerError,
    LocalA11yRunner,
)

A11yRunnerFactory = Callable[[RootConfig, SafetyDecision], A11yRunner]


class AccessibilityModule(SentinelModule):
    """the documentation accessibility checks wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "accessibility"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
        *,
        runner_factory: A11yRunnerFactory | None = None,
    ) -> None:
        super().__init__(config, safety_decision)
        self._uses_default_factory = runner_factory is None
        self._runner_factory: A11yRunnerFactory = runner_factory or _default_runner_factory

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        return

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        # SentinelModule.plan returns spec paths; the accessibility module
        # works in routes (strings), not specs. Returning an empty tuple
        # keeps the base-class contract satisfied without misleading the
        # orchestrator. The real route plan is resolved in `execute`.
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        # The module emits findings via `emit_findings` rather than
        # surfacing a Playwright RunnerOutcome. Return a placeholder so
        # the base-class signature is honored — the real work happens in
        # `_run_audit` below.
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
        a11y_outcome = getattr(self, "_last_outcome", None)
        if a11y_outcome is None:
            return ()
        artifact_paths = {
            page.route: f"a11y/{_route_slug(page.route)}.json" for page in a11y_outcome.pages
        }
        return findings_from_pages(
            pages=a11y_outcome.pages,
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
        a11y_outcome = getattr(self, "_last_outcome", None)
        if a11y_outcome is None:
            return {"pages": 0, "violations": 0}
        violations = sum(len(p.axe_violations) for p in a11y_outcome.pages)
        keyboard = sum(len(p.keyboard_issues) for p in a11y_outcome.pages)
        landmarks = sum(len(p.landmark_issues) for p in a11y_outcome.pages)
        names = sum(len(p.accessible_name_issues) for p in a11y_outcome.pages)
        return {
            "pages": len(a11y_outcome.pages),
            "axe_violations": violations,
            "keyboard_issues": keyboard,
            "landmark_issues": landmarks,
            "accessible_name_issues": names,
            "total_issues": a11y_outcome.total_issues,
            "duration_ms": a11y_outcome.duration_ms,
            "incomplete": int(a11y_outcome.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        a11y_outcome = getattr(self, "_last_outcome", None)
        if a11y_outcome is None or not a11y_outcome.pages:
            status: ModuleStatus = "skipped"
        elif a11y_outcome.incomplete:
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

    def _run_audit(self, ctx: ModuleContext) -> A11yRunOutcome:
        options = _read_options(ctx)
        routes = _resolve_routes(self._config, options)
        if not routes:
            return A11yRunOutcome(pages=(), incomplete=False, duration_ms=0)

        axe_tags = options.axe_tags or self._config.accessibility.axe.tags
        invocation = A11yInvocation(
            run_id=ctx.run_id,
            run_dir=ctx.run_dir,
            target=str(ctx.target.base_url),
            routes=tuple(routes),
            axe_tags=tuple(axe_tags),
            request_timeout_seconds=self._config.accessibility.request_timeout_seconds,
            keyboard_max_tabs=self._config.accessibility.keyboard_max_tabs,
        )
        runner = self._runner_factory(self._config, self._safety)
        try:
            return runner.run(invocation)
        except A11yRunnerError:
            # Bubble the typed error up; orchestrator records the module
            # as errored (CLAUDE §9 partial-failure contract).
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> AccessibilityModuleOptions:
    raw = ctx.options.get("accessibility") if "accessibility" in ctx.options else ctx.options
    if isinstance(raw, AccessibilityModuleOptions):
        return raw
    if isinstance(raw, dict):
        routes_value: Any = raw.get("routes") or ()
        if isinstance(routes_value, str):
            routes_tuple: tuple[str, ...] = (routes_value,)
        else:
            routes_tuple = tuple(str(r) for r in routes_value)
        axe_tags_value: Any = raw.get("axe_tags")
        axe_tags_tuple: tuple[str, ...] | None = (
            None if axe_tags_value is None else tuple(str(t) for t in axe_tags_value)
        )
        discovery_value: Any = raw.get("discovery_path")
        discovery_path: Path | None
        if discovery_value is None:
            discovery_path = None
        elif isinstance(discovery_value, Path):
            discovery_path = discovery_value
        else:
            discovery_path = Path(str(discovery_value))
        return AccessibilityModuleOptions(
            routes=routes_tuple,
            discovery_path=discovery_path,
            axe_tags=axe_tags_tuple,
            extra_env=raw.get("extra_env", {}),
        )
    return AccessibilityModuleOptions()


def _resolve_routes(
    config: RootConfig,
    options: AccessibilityModuleOptions,
) -> tuple[str, ...]:
    """Resolve the route set in priority order: CLI → discovery → config → default."""

    if options.routes:
        return tuple(_normalize_route(r) for r in options.routes)
    if options.discovery_path is not None:
        routes = _routes_from_discovery(options.discovery_path)
        if routes:
            return routes
    if config.accessibility.routes:
        return tuple(_normalize_route(r) for r in config.accessibility.routes)
    # When no caller (CLI / SDK / `sentinel audit`) has told us which routes to
    # audit, the module short-circuits instead of guessing — the same way
    # `FunctionalModule` returns an empty outcome when no specs exist.
    # `sentinel a11y` injects the `("/",)` fallback explicitly so the
    # standalone CLI still works against a localhost target.
    return ()


def _routes_from_discovery(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates: list[str] = []
    # discovery.json lists routes at `routes[*].path`.
    raw_routes = payload.get("routes") if isinstance(payload, dict) else None
    if isinstance(raw_routes, list):
        for entry in raw_routes:
            if isinstance(entry, dict):
                value = entry.get("path") or entry.get("route")
                if isinstance(value, str) and value:
                    candidates.append(value)
            elif isinstance(entry, str):
                candidates.append(entry)
    # Deduplicate while preserving order.
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


def _synthetic_runner_outcome(ctx: ModuleContext, a11y_outcome: A11yRunOutcome) -> RunnerOutcome:
    """Build a placeholder :class:`RunnerOutcome` so the base contract holds."""

    status: ModuleStatus = (
        "skipped"
        if not a11y_outcome.pages
        else ("incomplete" if a11y_outcome.incomplete else "passed")
    )
    return RunnerOutcome.build(
        module_name="accessibility",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=a11y_outcome.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _default_runner_factory(
    config: RootConfig,
    safety_decision: SafetyDecision,
) -> A11yRunner:
    return LocalA11yRunner(config=config, safety=safety_decision)


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> AccessibilityModule:
    return AccessibilityModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "accessibility" in reg.modules:
        return
    reg.register_module("accessibility", _factory)


_ = datetime.now(UTC)  # ensure timezone import isn't pruned by linters


__all__ = [
    "AccessibilityModule",
    "AccessibilityModuleOptions",
    "A11yRunnerFactory",
    "_factory",
    "register_with_default_registry",
]
