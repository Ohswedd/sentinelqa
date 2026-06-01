"""``FunctionalModule`` — the first concrete :class:`SentinelModule`.

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — refuses to run without a resolvable
  ``sentinel-ts`` binary OR an injected runner factory (tests).
- ``plan``                   — walks ``tests/sentinel/`` for
  ``*.spec.ts`` files, applying the optional grep / path filter.
- ``execute``                — calls the configured runner with
  ``module_name="functional"`` and the resolved spec set.
- ``collect_evidence``       — pass-through (evidence is already
  attached to each ``TestExecution`` by Phase 08 aggregation).
- ``emit_findings``          — base class default (one high-severity
  Finding per non-quarantined failure/timeout, with our product spec evidence).
- ``emit_metrics``           — base class default + ``flake_rate``.
- ``summarize``              — overlays findings on the runner's
  :class:`ModuleResult`.

The module exposes its runner factory as a constructor parameter so
tests can inject a stub (the Phase 08 CLI tests use the same shape).
Production code uses :func:`_default_runner_factory`, which picks
:class:`LocalRunner` or :class:`DockerRunner` based on
``config.runner.docker``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Protocol

from engine.config.schema import RootConfig
from engine.modules.base import ModuleContext, ModulePrerequisiteError, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from engine.runner import DockerRunner, LocalRunner, Quarantine, QuarantineError
from engine.runner.local import RunnerInvocation
from engine.runner.results import RunnerOutcome
from engine.runner.sharding import ShardSpec


class _RunnerLike(Protocol):
    """Structural type for runners (LocalRunner / DockerRunner / test stubs)."""

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:  # pragma: no cover
        ...


RunnerFactory = Callable[[RootConfig, SafetyDecision], _RunnerLike]


@dataclass(frozen=True)
class FunctionalModuleOptions:
    """Per-run inputs the orchestrator threads into the module via ``ctx.options``.

    All fields are optional. ``spec_root`` defaults to ``tests/sentinel/``;
    ``grep`` is forwarded to the Playwright runner as ``--grep <value>``;
    ``shard``/``workers`` are forwarded into :class:`RunnerInvocation`.
    """

    spec_root: Path | None = None
    grep: str | None = None
    shard: ShardSpec | None = None
    workers: int | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


class FunctionalModule(SentinelModule):
    """the documentation functional flows wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "functional"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
        *,
        runner_factory: RunnerFactory | None = None,
    ) -> None:
        super().__init__(config, safety_decision)
        # Remember whether the caller injected a factory so
        # validate_prerequisites can skip the sentinel-ts probe when a
        # test stub is in play. We can't rely on `is`-comparison against
        # the module global because tests routinely monkey-patch
        # ``_default_runner_factory`` itself.
        self._uses_default_factory = runner_factory is None
        self._runner_factory: RunnerFactory = runner_factory or _default_runner_factory

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        # Intentional no-op. The sentinel-ts probe lives inside
        # :meth:`execute` (and only fires when there are specs to run),
        # so ``sentinel audit`` against a project that hasn't generated
        # specs yet reports ``skipped`` instead of ``errored``.
        return

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        options = _read_options(ctx)
        spec_root = options.spec_root or (Path("tests") / "sentinel")
        if not spec_root.is_absolute():
            spec_root = Path.cwd() / spec_root
        if not spec_root.exists():
            return ()
        return tuple(sorted(spec_root.rglob("*.spec.ts")))

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        if not specs:
            # No specs → the runner will short-circuit; build an empty
            # outcome so the lifecycle can still produce a ModuleResult.
            return _empty_outcome(ctx)
        # Probe sentinel-ts here so the orchestrator records
        # ``skipped`` when there's nothing to run AND the runner is
        # missing — only blocking when both a spec exists and the
        # binary is unavailable.
        if self._uses_default_factory:
            from engine.runner.local import LocalRunner

            try:
                LocalRunner(config=self._config)._resolve_sentinel_ts()
            except Exception as exc:
                raise ModulePrerequisiteError(str(exc)) from exc
        options = _read_options(ctx)
        quarantine = _load_quarantine(self._config)
        invocation = RunnerInvocation(
            run_id=ctx.run_id,
            run_dir=ctx.run_dir,
            target=str(ctx.target.base_url),
            module_name=self.name,
            spec_files=specs,
            shard=options.shard,
            workers=options.workers,
            quarantine=quarantine,
            grep=options.grep,
        )
        runner = self._runner_factory(self._config, self._safety)
        return runner.run(invocation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> FunctionalModuleOptions:
    raw = ctx.options.get("functional") if "functional" in ctx.options else ctx.options
    if isinstance(raw, FunctionalModuleOptions):
        return raw
    if isinstance(raw, dict):
        return FunctionalModuleOptions(
            spec_root=_coerce_path(raw.get("spec_root")),
            grep=raw.get("grep"),
            shard=raw.get("shard"),
            workers=raw.get("workers"),
            extra_env=raw.get("extra_env", {}),
        )
    return FunctionalModuleOptions()


def _coerce_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(str(value))


def _load_quarantine(config: RootConfig) -> Quarantine:
    try:
        return Quarantine.load(
            config.runner.quarantine.path,
            max_age_days=config.runner.quarantine.max_age_days,
        )
    except QuarantineError:
        # If the quarantine is malformed at module-run time the CLI has
        # already surfaced the error. Inside the orchestrator (e.g.
        # `sentinel audit`) we fall back to an empty quarantine so the
        # module run can still emit a typed partial result (CLAUDE §9).
        return Quarantine.empty()


def _default_runner_factory(
    config: RootConfig,
    safety_decision: SafetyDecision,
) -> _RunnerLike:
    if config.runner.docker:
        from engine.domain.target import Target

        target = Target(
            base_url=config.target.base_url,
            allowed_hosts=frozenset(config.target.allowed_hosts),
            mode=config.security.mode,
            proof_of_authorization=config.target.proof_of_authorization,
        )
        from engine.policy.safety import SafetyPolicy

        return DockerRunner(
            config=config,
            target=target,
            safety_policy=SafetyPolicy(),
        )
    return LocalRunner(config=config)


def _empty_outcome(ctx: ModuleContext) -> RunnerOutcome:
    from engine.runner.results import EnvironmentContext

    return RunnerOutcome.build(
        module_name="functional",
        module_id=ctx.id_generator.new("MOD"),
        status="skipped",
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> FunctionalModule:
    """Default factory the orchestrator invokes for the ``functional`` module."""

    return FunctionalModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    """Idempotent registration helper.

    Calling this from ``modules.functional.__init__`` wires the module
    into the process-wide :class:`ModuleRegistry`. Tests that need a
    pristine registry construct their own instance, call
    ``registry.register_module(...)`` directly, and pass that registry
    into :class:`RunLifecycle`.
    """

    reg = registry or default_registry()
    if "functional" in reg.modules:
        return
    reg.register_module("functional", _factory)


__all__ = [
    "FunctionalModule",
    "FunctionalModuleOptions",
    "RunnerFactory",
    "_factory",
    "register_with_default_registry",
]
