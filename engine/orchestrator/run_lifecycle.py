"""Canonical run lifecycle (CLAUDE §10, ).

This file is the ONLY place the 17 lifecycle steps from CLAUDE §10 are
spelled out end-to-end. Module phases (05+) plug into individual steps
via :class:`engine.orchestrator.registry.ModuleRegistry`.

Module failures captured during step 10 (``run_modules``) do NOT abort
the run; they are recorded as :class:`engine.domain.module_result.ModuleResult`
with ``status="errored"``. Safety-policy and config-validation failures
DO abort, with the run marked ``unsafe_blocked`` / ``incomplete``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from engine.config.schema import RootConfig
from engine.domain.finding import Finding
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.target import Target
from engine.domain.test_run import RunStatus, TestRun
from engine.errors.base import (
    ConfigError,
    SentinelError,
    TestExecutionError,
    UnsafeTargetError,
)
from engine.log import get_logger, log_context
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import (
    LifecyclePhase,
    ModuleRegistry,
    default_registry,
)
from engine.orchestrator.symlinks import update_latest_pointer
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyDecision, SafetyPolicy

_LOGGER = get_logger("orchestrator.lifecycle")


@dataclass
class ModuleOutcome:
    """In-memory record of a single module invocation.

    When a module raises, 's analyzer classifies the error into
    one of the canonical :data:`engine.analyzer.models.FailureCategory`
    values (rehome of CLAUDE §10's broad ``except Exception`` per task
    09.01). The classification is exposed through ``error_category`` /
    ``error_confidence`` / ``error_rationale`` so the reporter and SDK
    can surface *why* a module fell over instead of just "errored".
    """

    name: str
    status: str  # "succeeded" | "errored" | "skipped"
    error_message: str | None = None
    error_type: str | None = None
    error_category: str | None = None
    error_confidence: float | None = None
    error_rationale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleContext:
    """Mutable per-run state threaded through the 17 steps."""

    config: RootConfig
    registry: ModuleRegistry
    requested_modules: list[str] | None
    dry_run: bool
    ci: bool
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    target: Target | None = None
    safety_decision: SafetyDecision | None = None
    run_id: str | None = None
    artifacts: ArtifactDirectory | None = None
    audit_log_path: Path | None = None
    config_snapshot_path: Path | None = None
    module_outcomes: list[ModuleOutcome] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    quality_score: dict[str, Any] = field(default_factory=dict)
    quality_gate_passed: bool = True
    status: RunStatus = "incomplete"
    early_exit: bool = False
    # +: typed domain objects passed to the Reporter when modules
    # produce them. Raw `findings` / `quality_score` above stay around
    # for the legacy dict path until retires them.
    typed_findings: tuple[Finding, ...] = field(default_factory=tuple)
    typed_module_results: tuple[ModuleResult, ...] = field(default_factory=tuple)
    typed_score: QualityScore | None = None
    typed_policy: PolicyDecision | None = None
    # +: per-module options threaded from the CLI / SDK.
    module_options: dict[str, Mapping[str, Any]] = field(default_factory=dict)


class RunLifecycle:
    """Stateless executor of the 17-step CLAUDE §10 lifecycle."""

    def __init__(
        self,
        *,
        artifacts_root: Path | None = None,
        registry: ModuleRegistry | None = None,
        safety_policy: SafetyPolicy | None = None,
    ) -> None:
        self._artifacts_root = artifacts_root or Path(".sentinel") / "runs"
        self._registry = registry or default_registry()
        self._safety = safety_policy or SafetyPolicy()
        self._ensure_default_hooks()
        # The last :class:`LifecycleContext` populated by ``execute``. The
        # CLI / SDK reads this immediately after a synchronous call to
        # ``execute`` to fetch typed module results + findings without
        # round-tripping through disk. Resets at the top of every ``execute``.
        self._last_context: LifecycleContext | None = None

    def _ensure_default_hooks(self) -> None:
        """Register the Phase-03 reporter + Phase-14 scoring hooks.

        Imported locally to avoid the orchestrator <-> reporter / scoring
        circular dependency. A sentinel flag on the registry keeps
        registration idempotent so tests that build fresh lifecycles
        don't double-register.
        """

        if not getattr(self._registry, "_reporter_hook_registered", False):
            from engine.reporter.dispatcher import register_reporter_hook

            register_reporter_hook(self._registry)
            self._registry._reporter_hook_registered = True  # type: ignore[attr-defined]
        if not getattr(self._registry, "_scoring_hooks_registered", False):
            from engine.scoring import register_scoring_hooks

            register_scoring_hooks(self._registry)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        config: RootConfig,
        *,
        requested_modules: list[str] | None = None,
        dry_run: bool = False,
        ci: bool = False,
        module_options: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> TestRun:
        """Run the lifecycle and return the finalized :class:`TestRun`.

        ``module_options`` lets the caller hand per-module knobs (spec
        root, grep, shard, workers) to the SentinelModule instance via
        ``ModuleContext.options``. Keys are module names; values are
        free-form mappings consumed by the module.
        """

        context = LifecycleContext(
            config=config,
            registry=self._registry,
            requested_modules=requested_modules,
            dry_run=dry_run,
            ci=ci,
            module_options=dict(module_options or {}),
        )
        # Expose the in-flight context to callers (the CLI reads typed
        # results immediately after ``execute`` returns). Cleared at top of
        # every ``execute`` so stale state from a previous run never leaks.
        self._last_context = context

        # Steps 1-2 happen before the run id exists so we can fail fast.
        self.load_config(context)
        self.validate_config(context)
        self.resolve_target(context)

        # Step 5 — create the run id early so subsequent logging has a
        # stable correlation id. (CLAUDE §10 lists this as step 5; we
        # promote it slightly so the safety audit log has a run id to
        # attach. The functional ordering is preserved — id is generated
        # before any module work.)
        self.create_run_id(context)
        self.create_artifact_directory(context)

        with log_context(run_id=context.run_id):
            try:
                self.enforce_safety_policy(context)
            except UnsafeTargetError as exc:
                context.status = "unsafe_blocked"
                context.early_exit = True
                self._finalize_unsafe(context, exc)
                return self._build_run(context)

            self.snapshot_config(context)
            self.discover_app(context)
            self.build_execution_plan(context)

            if context.dry_run:
                context.status = "dry_run"
                self._finalize_dry_run(context)
                return self._build_run(context)

            self.run_modules(context)
            self.collect_evidence(context)
            self.normalize_findings(context)
            self.calculate_quality_score(context)
            self.apply_quality_gates(context)
            self.generate_reports(context)
            self.persist_artifacts(context)
            self.return_deterministic_exit_code(context)
            return self._build_run(context)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def load_config(self, ctx: LifecycleContext) -> None:
        # Caller already called engine.config.loader.load_config; this
        # step verifies the snapshot is the expected type and freezes it
        # for the run.
        if not isinstance(ctx.config, RootConfig):
            raise ConfigError(
                detail=f"Expected RootConfig; got {type(ctx.config).__name__}.",
            )

    def validate_config(self, ctx: LifecycleContext) -> None:
        # Re-validate to catch any post-load mutation.
        try:
            RootConfig.model_validate(ctx.config.to_dict())
        except Exception as exc:
            raise ConfigError(detail=str(exc)) from exc

    def resolve_target(self, ctx: LifecycleContext) -> None:
        cfg = ctx.config
        target = Target(
            base_url=cfg.target.base_url,
            allowed_hosts=frozenset(cfg.target.allowed_hosts),
            mode=cfg.security.mode,
            proof_of_authorization=cfg.target.proof_of_authorization,
        )
        ctx.target = target
        parsed = urlparse(str(target.base_url))
        _LOGGER.debug(
            "resolved target",
            extra={"host": parsed.hostname, "mode": target.mode},
        )

    def enforce_safety_policy(self, ctx: LifecycleContext) -> None:
        assert ctx.target is not None
        assert ctx.audit_log_path is not None
        decision = self._safety.enforce(
            ctx.target,
            audit_log_path=ctx.audit_log_path,
        )
        ctx.safety_decision = decision
        _LOGGER.info(
            "safety policy allowed run",
            extra={"host": decision.host, "mode": decision.mode},
        )

    def create_run_id(self, ctx: LifecycleContext) -> None:
        ctx.run_id = IdGenerator().new("RUN")
        _LOGGER.info("created run id", extra={"run_id": ctx.run_id})

    def create_artifact_directory(self, ctx: LifecycleContext) -> None:
        assert ctx.run_id is not None
        ctx.artifacts = ArtifactDirectory.create(self._artifacts_root, ctx.run_id)
        ctx.audit_log_path = ctx.artifacts.path("audit.log")

    def snapshot_config(self, ctx: LifecycleContext) -> None:
        assert ctx.artifacts is not None
        ctx.config_snapshot_path = ctx.artifacts.write_yaml("config.snapshot.yaml", ctx.config)

    def discover_app(self, ctx: LifecycleContext) -> None:
        # Stub until. Phase hooks can override.
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.DISCOVER_APP, []):
            hook(ctx)

    def build_execution_plan(self, ctx: LifecycleContext) -> None:
        # owns the real planner. For now: surface the enabled
        # modules so dry-run output is informative.
        ctx.plan["modules"] = sorted(self._modules_to_run(ctx))
        ctx.plan["dry_run"] = ctx.dry_run
        ctx.plan["ci"] = ctx.ci
        assert ctx.artifacts is not None
        ctx.artifacts.write_json("plan.json", ctx.plan)
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.BUILD_EXECUTION_PLAN, []):
            hook(ctx)

    def run_modules(self, ctx: LifecycleContext) -> None:
        # Local import: the analyzer depends on engine.orchestrator.ts_bridge,
        # which is already loaded above. Importing here keeps the run-modules
        # path importable in test setups that monkey-patch the analyzer.
        from engine.analyzer.categorize import categorize_module_error
        from engine.modules.base import ModulePrerequisiteError, SentinelModule

        for name in self._modules_to_run(ctx):
            factory = ctx.registry.modules.get(name)
            if factory is None:
                ctx.module_outcomes.append(
                    ModuleOutcome(name=name, status="skipped", metadata={"reason": "no_factory"})
                )
                continue
            try:
                # Modules receive the config + safety decision; their
                # real interface lands in. For we
                # invoke and tolerate any callable. wraps the
                # SentinelModule lifecycle: if the factory returns a
                # SentinelModule instance we drive the seven CLAUDE §9
                # steps and merge findings/metrics into the context.
                result = factory(ctx.config, ctx.safety_decision)
                if isinstance(result, SentinelModule):
                    module_result = self._invoke_sentinel_module(ctx, name, result)
                    ctx.typed_module_results = (*ctx.typed_module_results, module_result)
                    ctx.typed_findings = (*ctx.typed_findings, *module_result.findings)
                    ctx.module_outcomes.append(
                        ModuleOutcome(
                            name=name,
                            status="succeeded",
                            metadata={
                                "module_result_id": module_result.id,
                                "module_status": module_result.status,
                                "findings": len(module_result.findings),
                            },
                        )
                    )
                else:
                    ctx.module_outcomes.append(
                        ModuleOutcome(
                            name=name, status="succeeded", metadata={"result": str(result)}
                        )
                    )
            except ModulePrerequisiteError as exc:
                classification = categorize_module_error(
                    module=name,
                    exc_type=type(exc).__name__,
                    exc_message=str(exc),
                )
                ctx.module_outcomes.append(
                    ModuleOutcome(
                        name=name,
                        status="errored",
                        error_message=str(exc),
                        error_type=type(exc).__name__,
                        error_category=classification.category,
                        error_confidence=classification.confidence,
                        error_rationale=classification.rationale,
                    )
                )
            except TestExecutionError as exc:
                classification = categorize_module_error(
                    module=name,
                    exc_type=type(exc).__name__,
                    exc_message=exc.message,
                )
                ctx.module_outcomes.append(
                    ModuleOutcome(
                        name=name,
                        status="errored",
                        error_message=exc.message,
                        error_type=type(exc).__name__,
                        error_category=classification.category,
                        error_confidence=classification.confidence,
                        error_rationale=classification.rationale,
                    )
                )
            except SentinelError as exc:
                classification = categorize_module_error(
                    module=name,
                    exc_type=type(exc).__name__,
                    exc_message=exc.message,
                )
                ctx.module_outcomes.append(
                    ModuleOutcome(
                        name=name,
                        status="errored",
                        error_message=exc.message,
                        error_type=type(exc).__name__,
                        error_category=classification.category,
                        error_confidence=classification.confidence,
                        error_rationale=classification.rationale,
                    )
                )
            except Exception as exc:
                classification = categorize_module_error(
                    module=name,
                    exc_type=type(exc).__name__,
                    exc_message=str(exc),
                )
                ctx.module_outcomes.append(
                    ModuleOutcome(
                        name=name,
                        status="errored",
                        error_message=f"{type(exc).__name__}: {exc}",
                        error_type=type(exc).__name__,
                        error_category=classification.category,
                        error_confidence=classification.confidence,
                        error_rationale=classification.rationale,
                    )
                )

    def collect_evidence(self, ctx: LifecycleContext) -> None:
        # Stub: when modules emit evidence (+), aggregate it here.
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.COLLECT_EVIDENCE, []):
            hook(ctx)

    def normalize_findings(self, ctx: LifecycleContext) -> None:
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.NORMALIZE_FINDINGS, []):
            hook(ctx)

    def calculate_quality_score(self, ctx: LifecycleContext) -> None:
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.CALCULATE_QUALITY_SCORE, []):
            hook(ctx)

    def apply_quality_gates(self, ctx: LifecycleContext) -> None:
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.APPLY_QUALITY_GATES, []):
            hook(ctx)

    def generate_reports(self, ctx: LifecycleContext) -> None:
        # Reports must carry the final status, so finalize before any
        # report hooks run. 's Reporter (registered on this
        # phase) writes run.json + report.md etc. with the correct
        # status; persist_artifacts then only handles the latest
        # pointer.
        ctx.finished_at = datetime.now(UTC)
        self._finalize_status(ctx)
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.GENERATE_REPORTS, []):
            hook(ctx)

    def persist_artifacts(self, ctx: LifecycleContext) -> None:
        # moved run.json / findings.json / score.json into the
        # Reporter (called from `generate_reports`). This step now only
        # finalizes the artifact directory (latest pointer) so the
        # canonical write path is single-source-of-truth.
        assert ctx.artifacts is not None
        if ctx.finished_at is None:
            ctx.finished_at = datetime.now(UTC)
            self._finalize_status(ctx)
        update_latest_pointer(self._artifacts_root, ctx.artifacts.root)

    def return_deterministic_exit_code(self, ctx: LifecycleContext) -> None:
        # Status was finalized in persist_artifacts; this step is the
        # canonical hand-off to the CLI exit-code mapping. The CLI reads
        # `test_run.status` and converts it to an exit code via
        # `engine.policy.exit_codes`.
        if ctx.status == "incomplete":
            _LOGGER.warning(
                "run completed with incomplete status",
                extra={"run_id": ctx.run_id},
            )

    def _finalize_status(self, ctx: LifecycleContext) -> None:
        errored = any(o.status == "errored" for o in ctx.module_outcomes)
        if not ctx.quality_gate_passed:
            ctx.status = "failed"
        elif errored:
            # Module errors mean we didn't complete every check. Mark
            # incomplete so reports stamp the run honestly (CLAUDE §10).
            ctx.status = "incomplete"
        else:
            ctx.status = "passed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def last_context(self) -> LifecycleContext | None:
        """Most recent :class:`LifecycleContext` populated by ``execute``.

        ``None`` before the first call. Callers should treat the context
        as read-only — the lifecycle owns its lifetime.
        """

        return self._last_context

    def _invoke_sentinel_module(
        self,
        ctx: LifecycleContext,
        module_name: str,
        module: Any,
    ) -> ModuleResult:
        """Drive a :class:`SentinelModule`'s seven-step lifecycle (CLAUDE §9)."""

        from engine.modules.base import ModuleContext

        assert ctx.artifacts is not None
        assert ctx.run_id is not None
        assert ctx.target is not None
        assert ctx.safety_decision is not None
        module_ctx = ModuleContext(
            module_name=module_name,
            config=ctx.config,
            safety_decision=ctx.safety_decision,
            artifacts=ctx.artifacts,
            run_id=ctx.run_id,
            run_dir=ctx.artifacts.root,
            target=ctx.target,
            id_generator=IdGenerator(),
            options=ctx.module_options.get(module_name, {}),
        )
        return module.run(module_ctx)  # type: ignore[no-any-return]

    def _modules_to_run(self, ctx: LifecycleContext) -> Iterable[str]:
        if ctx.requested_modules is not None:
            return list(ctx.requested_modules)
        enabled = []
        mods = ctx.config.modules
        if mods.functional:
            enabled.append("functional")
        if mods.api:
            enabled.append("api")
        if mods.accessibility:
            enabled.append("accessibility")
        if mods.performance:
            enabled.append("performance")
        if mods.visual:
            enabled.append("visual")
        if mods.security:
            enabled.append("security")
        if mods.chaos:
            enabled.append("chaos")
        if mods.llm_audit:
            enabled.append("llm_audit")
        return enabled

    def _finalize_unsafe(self, ctx: LifecycleContext, exc: UnsafeTargetError) -> None:
        ctx.finished_at = datetime.now(UTC)
        if ctx.artifacts is None or ctx.audit_log_path is None:
            return
        write_audit_entry(
            ctx.audit_log_path,
            {
                "event": "safety_block",
                "code": exc.code,
                "message": exc.message,
                "host": exc.technical_context.get("host"),
            },
        )
        self._write_short_circuit_run(ctx, errors=({"code": exc.code, "message": exc.message},))

    def _finalize_dry_run(self, ctx: LifecycleContext) -> None:
        ctx.finished_at = datetime.now(UTC)
        assert ctx.artifacts is not None
        self._write_short_circuit_run(ctx)
        update_latest_pointer(self._artifacts_root, ctx.artifacts.root)

    def _write_short_circuit_run(
        self,
        ctx: LifecycleContext,
        *,
        errors: tuple[Mapping[str, str], ...] = (),
    ) -> None:
        """Write ``run.json`` for the unsafe / dry-run early exits.

        Uses the same wire format as the happy path (`engine.reporter.run_writer.write_run`),
        so every successful and short-circuit run shares one schema. The
        full Reporter dispatcher is intentionally NOT invoked here — these
        exits have no findings/score/policy and no module ran, so only
        `run.json` + `audit.log` are produced (our engineering rules, §11).
        """

        from engine.reporter.run_writer import write_run

        assert ctx.artifacts is not None
        assert ctx.target is not None
        assert ctx.run_id is not None
        test_run = TestRun(
            id=ctx.run_id,
            started_at=ctx.started_at,
            finished_at=ctx.finished_at,
            target=ctx.target,
            config_snapshot=ctx.config.to_dict(),
            modules_run=tuple(sorted({o.name for o in ctx.module_outcomes})),
            status=ctx.status,
        )
        # Short-circuit paths never reach generate_reports, so no other
        # artifact_paths slot is populated; only audit.log is guaranteed
        # to exist (the unsafe path always writes it; dry_run runs after
        # safety enforcement which already wrote the safety_allowed line).
        artifact_paths: dict[str, str | None] = {
            "findings": None,
            "score": None,
            "junit": None,
            "sarif": None,
            "report_html": None,
            "report_md": None,
            "audit_log": "audit.log",
        }
        write_run(
            ctx.artifacts,
            test_run,
            config_snapshot=ctx.config.to_dict(),
            errors=errors,
            artifact_paths=artifact_paths,
        )

    def _build_run(self, ctx: LifecycleContext) -> TestRun:
        assert ctx.target is not None
        return TestRun(
            id=ctx.run_id or IdGenerator().new("RUN"),
            started_at=ctx.started_at,
            finished_at=ctx.finished_at,
            target=ctx.target,
            config_snapshot=ctx.config.to_dict(),
            modules_run=tuple(sorted({o.name for o in ctx.module_outcomes})),
            status=ctx.status,
        )


__all__ = ["LifecycleContext", "ModuleOutcome", "RunLifecycle"]
