"""Canonical run lifecycle (CLAUDE §10, task 02.04).

This file is the ONLY place the 17 lifecycle steps from CLAUDE §10 are
spelled out end-to-end. Module phases (05+) plug into individual steps
via :class:`engine.orchestrator.registry.ModuleRegistry`.

Module failures captured during step 10 (``run_modules``) do NOT abort
the run; they are recorded as :class:`engine.domain.module_result.ModuleResult`
with ``status="errored"``. Safety-policy and config-validation failures
DO abort, with the run marked ``unsafe_blocked`` / ``incomplete``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from engine.config.schema import RootConfig
from engine.domain.ids import IdGenerator
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
    """In-memory record of a single module invocation."""

    name: str
    status: str  # "succeeded" | "errored" | "skipped"
    error_message: str | None = None
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
    ) -> TestRun:
        """Run the lifecycle and return the finalized :class:`TestRun`."""

        context = LifecycleContext(
            config=config,
            registry=self._registry,
            requested_modules=requested_modules,
            dry_run=dry_run,
            ci=ci,
        )

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
        # Stub until Phase 05. Phase hooks can override.
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.DISCOVER_APP, []):
            hook(ctx)

    def build_execution_plan(self, ctx: LifecycleContext) -> None:
        # Phase 06 owns the real planner. For now: surface the enabled
        # modules so dry-run output is informative.
        ctx.plan["modules"] = sorted(self._modules_to_run(ctx))
        ctx.plan["dry_run"] = ctx.dry_run
        ctx.plan["ci"] = ctx.ci
        assert ctx.artifacts is not None
        ctx.artifacts.write_json("plan.json", ctx.plan)
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.BUILD_EXECUTION_PLAN, []):
            hook(ctx)

    def run_modules(self, ctx: LifecycleContext) -> None:
        for name in self._modules_to_run(ctx):
            factory = ctx.registry.modules.get(name)
            if factory is None:
                ctx.module_outcomes.append(
                    ModuleOutcome(name=name, status="skipped", metadata={"reason": "no_factory"})
                )
                continue
            try:
                # Modules receive the config + safety decision; their
                # real interface lands in Phase 24. For Phase 02 we
                # invoke and tolerate any callable.
                result = factory(ctx.config, ctx.safety_decision)
                ctx.module_outcomes.append(
                    ModuleOutcome(name=name, status="succeeded", metadata={"result": str(result)})
                )
            except TestExecutionError as exc:
                ctx.module_outcomes.append(
                    ModuleOutcome(name=name, status="errored", error_message=exc.message)
                )
            except SentinelError as exc:
                ctx.module_outcomes.append(
                    ModuleOutcome(name=name, status="errored", error_message=exc.message)
                )
            except Exception as exc:
                ctx.module_outcomes.append(
                    ModuleOutcome(
                        name=name,
                        status="errored",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )

    def collect_evidence(self, ctx: LifecycleContext) -> None:
        # Stub: when modules emit evidence (Phase 03+), aggregate it here.
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
        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.GENERATE_REPORTS, []):
            hook(ctx)

    def persist_artifacts(self, ctx: LifecycleContext) -> None:
        # CLAUDE §10 lists "persist artifacts" before "return deterministic
        # exit code". The persisted `run.json` must carry the final status,
        # so we compute the status first and then write artifacts. The
        # `return_deterministic_exit_code` step still owns the exit-code
        # mapping for the CLI boundary.
        assert ctx.artifacts is not None
        ctx.finished_at = datetime.now(UTC)
        self._finalize_status(ctx)
        run_payload = self._run_payload(ctx)
        ctx.artifacts.write_json("run.json", run_payload)
        if ctx.findings:
            ctx.artifacts.write_json("findings.json", {"findings": ctx.findings})
        if ctx.quality_score:
            ctx.artifacts.write_json("score.json", ctx.quality_score)
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
        if ctx.artifacts is not None and ctx.audit_log_path is not None:
            write_audit_entry(
                ctx.audit_log_path,
                {
                    "event": "safety_block",
                    "code": exc.code,
                    "message": exc.message,
                    "host": exc.technical_context.get("host"),
                },
            )
            ctx.artifacts.write_json("run.json", self._run_payload(ctx))

    def _finalize_dry_run(self, ctx: LifecycleContext) -> None:
        ctx.finished_at = datetime.now(UTC)
        assert ctx.artifacts is not None
        ctx.artifacts.write_json("run.json", self._run_payload(ctx))
        update_latest_pointer(self._artifacts_root, ctx.artifacts.root)

    def _run_payload(self, ctx: LifecycleContext) -> dict[str, Any]:
        return {
            "id": ctx.run_id,
            "started_at": ctx.started_at.isoformat(),
            "finished_at": (ctx.finished_at.isoformat() if ctx.finished_at else None),
            "status": ctx.status,
            "target": (ctx.target.to_dict() if ctx.target is not None else None),
            "modules_run": sorted({o.name for o in ctx.module_outcomes}),
            "module_outcomes": [
                {
                    "name": o.name,
                    "status": o.status,
                    "error_message": o.error_message,
                }
                for o in ctx.module_outcomes
            ],
            "config_snapshot": ctx.config.to_dict(),
            "schema_version": TestRun.SCHEMA_VERSION,
        }

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
