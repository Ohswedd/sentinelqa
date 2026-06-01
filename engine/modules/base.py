"""Abstract :class:`SentinelModule` (our engineering rules, our product spec, §10).

Every module follows the same lifecycle:

1. ``validate_prerequisites`` — refuse to run when the environment is wrong
 (missing binary, missing fixture, etc.).
2. ``plan`` — pick the subset of work this run cares about.
3. ``execute`` — drive the runner / external tool.
4. ``collect_evidence`` — gather artifacts (already on disk from the runner).
5. ``emit_findings`` — translate failures into typed :class:`Finding` records
 with our product spec evidence.
6. ``emit_metrics`` — derived from the runner outcome.
7. ``summarize`` — return the final :class:`ModuleResult`.

The orchestrator (``engine.orchestrator.run_lifecycle.RunLifecycle.run_modules``)
detects modules whose factory returns a :class:`SentinelModule` instance and
invokes :meth:`SentinelModule.run`, which threads the seven steps in order
and tolerates partial failure (CLAUDE §9: "a module failure should produce
a typed partial result unless the failure invalidates the entire run").

The module owns:

- Its own runner invocation.
- Its own findings translation (our product spec, §20).
- Its own metrics derivation.

The module does NOT own:

- Run lifecycle state (CLAUDE §10).
- Quality scoring.
- Report generation ( / ).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from engine.config.schema import RootConfig
from engine.domain.evidence import Evidence, EvidenceType
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.domain.target import Target
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from engine.runner.results import RunnerOutcome, TestExecution


class ModulePrerequisiteError(RuntimeError):
    """Raised by ``validate_prerequisites`` when the environment is unfit.

    The orchestrator catches this and records the module as ``errored``
    with the message + a derived category (CLAUDE §9, §10).
    """


@dataclass(frozen=True)
class ModuleContext:
    """Inputs the orchestrator hands to a :class:`SentinelModule` per run.

    Modules MUST treat the context as immutable. Mutating state goes back
    to the orchestrator via the returned :class:`ModuleResult` (CLAUDE §9).
    """

    module_name: str
    config: RootConfig
    safety_decision: SafetyDecision
    artifacts: ArtifactDirectory
    run_id: str
    run_dir: Path
    target: Target
    id_generator: IdGenerator
    options: Mapping[str, Any] = field(default_factory=dict)


class SentinelModule(ABC):
    """Common ancestor for every SentinelQA audit module.

    Subclasses set ``name`` and implement at minimum :meth:`execute` and
    :meth:`summarize`. The other hooks default to no-ops so simple modules
    don't have to override boilerplate.
    """

    name: ClassVar[str]
    """Canonical module name (matches ``ctx.module_name`` and config keys)."""

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        self._config = config
        self._safety = safety_decision

    # ------------------------------------------------------------------
    # Lifecycle steps — override as needed
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:  # noqa: B027
        """Raise :class:`ModulePrerequisiteError` if the env is unfit.

        Default is intentionally a no-op so subclasses override only when
        they actually have a prerequisite to enforce.
        """

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        """Return the specs/work items this module will exercise.

        Default implementation walks the standard spec root
        (``tests/sentinel/``) for ``*.spec.ts`` files.
        """

        spec_root = Path("tests") / "sentinel"
        if not spec_root.exists():
            return ()
        return tuple(sorted(spec_root.rglob("*.spec.ts")))

    @abstractmethod
    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        """Run the planned work and return a typed :class:`RunnerOutcome`."""

    def collect_evidence(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Evidence, ...]:
        """Hook for modules that aggregate post-run evidence; default no-op."""

        return ()

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        """Translate failed/timed_out tests into :class:`Finding` records.

        Default: one finding per non-quarantined failed/timed_out test.
        Severity comes from :func:`_default_severity`; subclasses override
        for module-specific severity policies.
        """

        findings: list[Finding] = []
        quarantined = set(outcome.quarantined_test_ids)
        for test in outcome.tests:
            if test.test_id in quarantined:
                continue
            if test.status not in {"failed", "timed_out"}:
                continue
            finding = build_finding_from_failed_test(
                test=test,
                module_name=self.name,
                run_id=ctx.run_id,
                target_base_url=str(ctx.target.base_url),
                id_generator=ctx.id_generator,
                severity=self._severity_for(test),
            )
            findings.append(finding)
        return tuple(findings)

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        """Default: pass through the runner-derived metrics."""

        return dict(outcome.module_result.metrics)

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        """Return the final :class:`ModuleResult` for this module's run.

        Default reuses the runner's :class:`ModuleResult` but overlays the
        emitted findings + metrics so the orchestrator sees a single
        consistent record.
        """

        merged_metrics = dict(outcome.module_result.metrics)
        merged_metrics.update(metrics)
        return outcome.module_result.model_copy(
            update={
                "findings": tuple(findings),
                "metrics": merged_metrics,
                "status": derive_module_status(outcome, findings),
            }
        )

    # ------------------------------------------------------------------
    # Orchestrator entry point
    # ------------------------------------------------------------------

    def run(self, ctx: ModuleContext) -> ModuleResult:
        """Run the seven-step lifecycle and return a :class:`ModuleResult`.

        The orchestrator (``RunLifecycle.run_modules``) calls this for each
        registered :class:`SentinelModule`. Exceptions bubble up so the
        orchestrator records them as ``errored`` ModuleOutcomes.
        """

        self.validate_prerequisites(ctx)
        specs = tuple(self.plan(ctx))
        outcome = self.execute(ctx, specs)
        self.collect_evidence(ctx, outcome)
        findings = self.emit_findings(ctx, outcome)
        metrics = self.emit_metrics(ctx, outcome)
        return self.summarize(ctx, outcome, findings, metrics)

    # ------------------------------------------------------------------
    # Hooks subclasses may override
    # ------------------------------------------------------------------

    def _severity_for(self, test: TestExecution) -> Severity:
        """Default severity assigned to a failed/timed-out test.

        Functional failures are treated as ``high`` by default; the spec
        author can override via tag annotations once wires
        severity overrides into the scoring layer.
        """

        return "high" if test.status == "failed" else "medium"


# ---------------------------------------------------------------------------
# Helpers reused by concrete modules + tests
# ---------------------------------------------------------------------------


def derive_module_status(
    outcome: RunnerOutcome,
    findings: Sequence[Finding],
) -> ModuleStatus:
    """Return the effective module status given the runner outcome + findings.

    Rules:

    - If the runner reported ``incomplete`` / ``errored`` / ``skipped``,
    preserve it (those are honest signals).
    - Otherwise, if any finding is critical/high, the module is ``failed``.
    - Otherwise, mirror the runner's status.
    """

    runner_status = outcome.module_result.status
    if runner_status in {"incomplete", "errored", "skipped"}:
        return runner_status
    blocking = any(f.severity in {"critical", "high"} for f in findings)
    if blocking:
        return "failed"
    return runner_status


def build_finding_from_failed_test(
    *,
    test: TestExecution,
    module_name: str,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    severity: Severity,
) -> Finding:
    """Translate a failed :class:`TestExecution` into a :class:`Finding`.

    Evidence pulled from ``test.evidence`` is recorded as relative paths
    (per CLAUDE §11), and each artifact is exposed as a typed
    :class:`Evidence` record so our product spec / §24 consumers (Reporter, SDK)
    can render them.
    """

    evidence_paths = list(test.evidence)
    if not evidence_paths:
        # our product spec requires every medium+ finding to carry evidence. When
        # the runner couldn't capture a trace / screenshot (e.g. the test
        # fixture had none) we fall back to the per-module runner log,
        # which always writes under ``logs/runner.<module>.log``.
        evidence_paths.append(f"logs/runner.{module_name}.log")
    evidence_records: tuple[Evidence, ...] = tuple(
        Evidence(
            id=id_generator.new("EVD"),
            type=_classify_evidence(path),
            path=Path(path),
        )
        for path in evidence_paths
    )
    failure_message = (test.error_message or "test failed without an error message").strip()
    truncated = failure_message[:1500]
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module=module_name,
        category=_category_for_test(test),
        severity=severity,
        confidence=0.9,
        title=f"{test.title} ({test.status})",
        description=(
            f"Functional test {test.test_id!r} ended with status "
            f"{test.status!r}. Failure detail: {truncated}"
        ),
        location=FindingLocation(file=test.file),
        evidence=evidence_records,
        reproduction_steps=(
            f"Open the captured trace for test {test.test_id!r}.",
            f"Replay the spec at {test.file}.",
        ),
        affected_target=target_base_url,
        recommendation=(
            "Inspect the captured trace, screenshot, and runner log. "
            "If the failure reproduces consistently, file a regression test "
            "for the underlying defect; if intermittent, escalate via "
            "Phase 09 analyzer + quarantine flow."
        ),
        created_at=datetime.now(UTC),
    )


def _classify_evidence(path: str) -> EvidenceType:
    lowered = path.lower()
    if lowered.endswith((".png", ".jpg", ".jpeg")):
        return "screenshot"
    if lowered.endswith((".webm", ".mp4")):
        return "video"
    if lowered.endswith(".zip"):
        return "trace"
    if lowered.endswith(".har"):
        return "har"
    if lowered.endswith((".log", ".txt")):
        return "console_log"
    if lowered.endswith(".html"):
        return "dom_snapshot"
    return "source_ref"


def _category_for_test(test: TestExecution) -> str:
    if test.status == "timed_out":
        return "functional_timeout"
    return "functional_failure"


__all__ = [
    "ModuleContext",
    "ModulePrerequisiteError",
    "SentinelModule",
    "build_finding_from_failed_test",
    "derive_module_status",
]
