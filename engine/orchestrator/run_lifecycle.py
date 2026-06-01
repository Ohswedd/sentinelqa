"""Canonical run lifecycle.

This file is the ONLY place the 17 lifecycle steps from the engineering guidelines
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

from engine.cache import CacheStore, SourceFingerprint, compute_fingerprint
from engine.cache.run_info import (
    CachePhaseInfo,
    CacheReport,
    FingerprintInfo,
    write_cache_report,
)
from engine.cache.store import default_cache_root
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
    values (rehome of the engineering guidelines's broad ``except Exception`` per task
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
    # v1.2.0: test-economics cache plumbing. ``source_fingerprint`` is
    # computed once before discovery (cheap content hash) so the
    # discovery and plan steps can do constant-time cache lookups.
    # Hit/miss is recorded under cache.json for the --since command.
    source_fingerprint: SourceFingerprint | None = None
    discovery_cache_hit: bool | None = None
    discovery_cache_key: str | None = None
    plan_cache_hit: bool | None = None
    plan_cache_key: str | None = None
    # v1.2.0: bounded concurrency for run_modules. ``module_concurrency=1``
    # preserves the original sequential behaviour.
    module_concurrency: int = 1


class RunLifecycle:
    """Stateless executor of the 17-step the engineering guidelines"""

    def __init__(
        self,
        *,
        artifacts_root: Path | None = None,
        registry: ModuleRegistry | None = None,
        safety_policy: SafetyPolicy | None = None,
        project_root: Path | None = None,
        cache_store: CacheStore | None = None,
    ) -> None:
        self._artifacts_root = artifacts_root or Path(".sentinel") / "runs"
        self._registry = registry or default_registry()
        self._safety = safety_policy or SafetyPolicy()
        # v1.2.0: ``project_root`` is the directory whose source we hash
        # for the cache + ``--since`` features. Defaults to CWD so existing
        # callers do not need to pass it. ``cache_store`` defaults to the
        # conventional ``.sentinel/cache/`` under the project root.
        self._project_root = (project_root or Path.cwd()).resolve()
        self._cache_store = cache_store or CacheStore(default_cache_root(self._project_root))
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
        module_concurrency: int = 1,
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
            module_concurrency=max(1, int(module_concurrency)),
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
        # stable correlation id. (the engineering guidelines; we
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
        # v1.2.0: compute the source fingerprint once per run (cheap, the
        # exclude set keeps this O(source files)). Failures here are
        # non-fatal — the cache simply degrades to "always miss".
        try:
            ctx.source_fingerprint = compute_fingerprint(self._project_root)
        except OSError:
            ctx.source_fingerprint = None

        # Discovery cache lookup: if a hook produced a discovery.json on
        # a prior run with the same fingerprint we restore it here.
        # Hooks still run afterwards (they may add evidence beyond what
        # the cached payload carries).
        assert ctx.artifacts is not None
        if ctx.source_fingerprint is not None:
            key = f"v1.{ctx.source_fingerprint.hash}"
            ctx.discovery_cache_key = key
            cached = self._cache_store.get("discovery", key)
            if cached is not None:
                ctx.artifacts.path("discovery.json").write_bytes(cached)
                ctx.discovery_cache_hit = True
                _LOGGER.info(
                    "discovery cache hit",
                    extra={"fingerprint": ctx.source_fingerprint.short()},
                )
            else:
                ctx.discovery_cache_hit = False

        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.DISCOVER_APP, []):
            hook(ctx)

        # Persist any hook-produced discovery.json into the cache for
        # the next run with the same fingerprint.
        if ctx.source_fingerprint is not None and ctx.discovery_cache_hit is False:
            artifact = ctx.artifacts.path("discovery.json")
            if artifact.is_file():
                import contextlib

                with contextlib.suppress(OSError):
                    self._cache_store.put(
                        "discovery", ctx.discovery_cache_key or "", artifact.read_bytes()
                    )

    def build_execution_plan(self, ctx: LifecycleContext) -> None:
        # v1.2.0: plan cache. The key encodes the source fingerprint AND
        # the requested-module set so that two runs with the same source
        # but different ``--modules`` produce different cache entries.
        assert ctx.artifacts is not None
        modules = sorted(self._modules_to_run(ctx))
        modules_sig = ",".join(modules) or "all"
        # Replace commas (cache-key-illegal) with dashes; modules_sig is
        # already restricted to module-name chars + the separator.
        modules_sig_safe = modules_sig.replace(",", "-")

        if ctx.source_fingerprint is not None:
            ctx.plan_cache_key = f"v1.{ctx.source_fingerprint.hash}.{modules_sig_safe}"
            cached = self._cache_store.get("plan", ctx.plan_cache_key)
            if cached is not None:
                ctx.artifacts.path("plan.json").write_bytes(cached)
                ctx.plan_cache_hit = True
                # Re-materialise the dict so downstream hooks see the
                # same plan whether we cached or recomputed it.
                import json as _json

                ctx.plan = _json.loads(cached.decode("utf-8"))
                _LOGGER.info("plan cache hit", extra={"key": ctx.plan_cache_key[:20]})
                for hook in ctx.registry.phase_hooks.get(LifecyclePhase.BUILD_EXECUTION_PLAN, []):
                    hook(ctx)
                return
            ctx.plan_cache_hit = False

        ctx.plan["modules"] = modules
        ctx.plan["dry_run"] = ctx.dry_run
        ctx.plan["ci"] = ctx.ci
        ctx.artifacts.write_json("plan.json", ctx.plan)

        # Persist to plan cache after writing the artifact.
        if (
            ctx.source_fingerprint is not None
            and ctx.plan_cache_hit is False
            and ctx.plan_cache_key is not None
        ):
            import contextlib

            with contextlib.suppress(OSError):
                self._cache_store.put(
                    "plan",
                    ctx.plan_cache_key,
                    ctx.artifacts.path("plan.json").read_bytes(),
                )

        for hook in ctx.registry.phase_hooks.get(LifecyclePhase.BUILD_EXECUTION_PLAN, []):
            hook(ctx)

    def run_modules(self, ctx: LifecycleContext) -> None:
        """Execute every requested module — sequentially or on a thread pool.

        v1.2.0: when ``ctx.module_concurrency > 1`` modules run on a
        bounded :class:`concurrent.futures.ThreadPoolExecutor`. Safety
        enforcement has already happened (step 6, before discovery), so
        no module reaches the network ahead of the policy. Outcomes are
        merged back into the context in the *input* order — deterministic
        output regardless of which thread finishes first.
        """

        names = list(self._modules_to_run(ctx))
        if not names:
            return

        concurrency = max(1, min(ctx.module_concurrency, len(names)))
        if concurrency == 1:
            for name in names:
                outcome, typed = self._execute_one_module(ctx, name)
                self._merge_module_result(ctx, outcome, typed)
            return

        # Parallel path. We snapshot the futures keyed by index so the
        # input order survives whatever order they complete in.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="sentinel-module"
        ) as pool:
            futures = [pool.submit(self._execute_one_module, ctx, name) for name in names]
            for future in futures:
                outcome, typed = future.result()
                self._merge_module_result(ctx, outcome, typed)

    def _execute_one_module(
        self,
        ctx: LifecycleContext,
        name: str,
    ) -> tuple[ModuleOutcome, ModuleResult | None]:
        """Run a single module and return its (outcome, optional ModuleResult).

        Pure for parallel-safety — no writes to ``ctx`` happen here.
        The parent thread merges results in input order via
        :meth:`_merge_module_result`.
        """

        from engine.analyzer.categorize import categorize_module_error
        from engine.modules.base import ModulePrerequisiteError, SentinelModule

        factory = ctx.registry.modules.get(name)
        if factory is None:
            return (
                ModuleOutcome(name=name, status="skipped", metadata={"reason": "no_factory"}),
                None,
            )

        try:
            result = factory(ctx.config, ctx.safety_decision)
            if isinstance(result, SentinelModule):
                module_result = self._invoke_sentinel_module(ctx, name, result)
                return (
                    ModuleOutcome(
                        name=name,
                        status="succeeded",
                        metadata={
                            "module_result_id": module_result.id,
                            "module_status": module_result.status,
                            "findings": len(module_result.findings),
                        },
                    ),
                    module_result,
                )
            return (
                ModuleOutcome(name=name, status="succeeded", metadata={"result": str(result)}),
                None,
            )
        except (ModulePrerequisiteError, TestExecutionError, SentinelError) as exc:
            message = (
                exc.message if isinstance(exc, TestExecutionError | SentinelError) else str(exc)
            )
            classification = categorize_module_error(
                module=name, exc_type=type(exc).__name__, exc_message=message
            )
            return (
                ModuleOutcome(
                    name=name,
                    status="errored",
                    error_message=message,
                    error_type=type(exc).__name__,
                    error_category=classification.category,
                    error_confidence=classification.confidence,
                    error_rationale=classification.rationale,
                ),
                None,
            )
        except Exception as exc:
            classification = categorize_module_error(
                module=name, exc_type=type(exc).__name__, exc_message=str(exc)
            )
            return (
                ModuleOutcome(
                    name=name,
                    status="errored",
                    error_message=f"{type(exc).__name__}: {exc}",
                    error_type=type(exc).__name__,
                    error_category=classification.category,
                    error_confidence=classification.confidence,
                    error_rationale=classification.rationale,
                ),
                None,
            )

    def _merge_module_result(
        self,
        ctx: LifecycleContext,
        outcome: ModuleOutcome,
        typed: ModuleResult | None,
    ) -> None:
        """Append a worker's (outcome, typed?) tuple back into the context.

        Always called on the main thread, in the same input order the
        modules were submitted in, so the resulting ``module_outcomes`` /
        ``typed_module_results`` tuples are byte-identical to the
        sequential path.
        """

        ctx.module_outcomes.append(outcome)
        if typed is not None:
            ctx.typed_module_results = (*ctx.typed_module_results, typed)
            ctx.typed_findings = (*ctx.typed_findings, *typed.findings)

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
        self._write_cache_report(ctx)
        update_latest_pointer(self._artifacts_root, ctx.artifacts.root)

    def _write_cache_report(self, ctx: LifecycleContext) -> None:
        """Write ``cache.json`` so the next run's ``--since`` can read it."""

        assert ctx.artifacts is not None
        fp_info = (
            FingerprintInfo(
                hash=ctx.source_fingerprint.hash,
                short=ctx.source_fingerprint.short(),
                file_count=ctx.source_fingerprint.file_count,
                total_bytes=ctx.source_fingerprint.total_bytes,
            )
            if ctx.source_fingerprint is not None
            else None
        )
        report = CacheReport(
            source_fingerprint=fp_info,
            discovery=CachePhaseInfo(
                cache_hit=ctx.discovery_cache_hit,
                cache_key=ctx.discovery_cache_key,
            ),
            plan=CachePhaseInfo(
                cache_hit=ctx.plan_cache_hit,
                cache_key=ctx.plan_cache_key,
            ),
        )
        write_cache_report(ctx.artifacts.path("cache.json"), report)

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
            # incomplete so reports stamp the run honestly.
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
        """Drive a :class:`SentinelModule`'s seven-step lifecycle."""

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
        self._write_cache_report(ctx)
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
