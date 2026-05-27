"""Reporter dispatcher (task 03.07).

The ``Reporter`` class wires every Phase-03 writer into a single entry
point that the run lifecycle calls during step 15 (``generate_reports``).
Formats are selected from ``config.report.formats``; absent formats are
skipped silently so the lifecycle can opt out without ceremony.

Each successful emit produces one ``artifact_emitted`` line in the
run's audit log (CLAUDE.md §11), so downstream reviewers always know
which formats were generated.

Phase 24 will replace the ad-hoc dispatch with a plugin entry-point
discovery mechanism; the :class:`ReporterPlugin` Protocol below is the
intended seam.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, Protocol, runtime_checkable

from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.audit_log import write_audit_entry
from engine.reporter.findings_writer import write_findings
from engine.reporter.junit_writer import write_junit
from engine.reporter.markdown_writer import write_markdown
from engine.reporter.run_writer import write_run
from engine.reporter.sarif_rules import SarifRuleRegistry
from engine.reporter.sarif_writer import write_sarif
from engine.reporter.score_writer import write_score

ReportFormat = Literal[
    "html",
    "json",  # alias: run + findings + score
    "junit",
    "sarif",
    "markdown",
    "run",
    "findings",
    "score",
]

SUPPORTED_FORMATS: Final[tuple[str, ...]] = (
    "run",
    "findings",
    "score",
    "junit",
    "sarif",
    "markdown",
)

# Config-level aliases (PRD §17.1 `report.formats`).
_FORMAT_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "json": ("run", "findings", "score"),
    "html": (),  # placeholder until Phase 15
}


@dataclass(frozen=True)
class ReportInputs:
    """Bundle of typed inputs the Reporter needs.

    Constructed by the orchestrator hook from the lifecycle context so
    the rest of the pipeline never depends on lifecycle internals.
    """

    run: TestRun
    findings: tuple[Finding, ...] = ()
    module_results: tuple[ModuleResult, ...] = ()
    score: QualityScore | None = None
    policy: PolicyDecision | None = None
    config_snapshot: Mapping[str, Any] = field(default_factory=dict)
    policy_config: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[Mapping[str, str], ...] = ()
    system_out: str | None = None


@runtime_checkable
class ReporterPlugin(Protocol):
    """Future plugin contract (Phase 24).

    A plugin declares the format names it handles and a callable that
    receives the typed inputs + the artifact directory. Phase 03 ships
    only the protocol; the dispatcher below registers built-ins
    directly via a switch.
    """

    name: str
    formats: tuple[str, ...]

    def emit(
        self,
        inputs: ReportInputs,
        artifact_dir: ArtifactDirectory,
    ) -> dict[str, Path]: ...


class Reporter:
    """Coordinates Phase-03 writers behind a single ``emit`` method.

    Construct once per run (or once per process for stateless use).
    Inject a :class:`SarifRuleRegistry` to pre-populate the SARIF
    writer's rule set; otherwise the process-wide default is used.
    """

    def __init__(
        self,
        *,
        sarif_registry: SarifRuleRegistry | None = None,
    ) -> None:
        self._sarif_registry = sarif_registry

    def emit(
        self,
        inputs: ReportInputs,
        artifact_dir: ArtifactDirectory,
        formats: Sequence[str],
        *,
        audit_log_path: Path | None = None,
    ) -> dict[str, Path]:
        """Emit every requested format. Returns ``{format_name: Path}``."""

        expanded = self._expand_formats(formats)
        # run.json is the canonical lifecycle artifact (CLAUDE.md §11);
        # it is ALWAYS written regardless of `formats` so the run record
        # is never silently dropped.
        expanded.add("run")
        artifact_paths = self._artifact_paths_map(expanded)
        outputs: dict[str, Path] = {}

        if "run" in expanded:
            outputs["run"] = write_run(
                artifact_dir,
                inputs.run,
                config_snapshot=inputs.config_snapshot,
                findings=inputs.findings,
                module_results=inputs.module_results,
                score=inputs.score,
                policy=inputs.policy,
                errors=inputs.errors,
                artifact_paths=artifact_paths,
            )

        if "findings" in expanded and inputs.findings:
            outputs["findings"] = write_findings(
                artifact_dir,
                inputs.findings,
                run_id=inputs.run.id,
                generated_at=inputs.run.finished_at,
            )

        if "score" in expanded:
            outputs["score"] = write_score(
                artifact_dir,
                run_id=inputs.run.id,
                score=inputs.score,
                policy_decision=inputs.policy,
                policy_config=inputs.policy_config,
            )

        if "junit" in expanded:
            outputs["junit"] = write_junit(
                artifact_dir,
                inputs.run,
                module_results=inputs.module_results,
                findings=inputs.findings,
                system_out=inputs.system_out,
            )

        if "sarif" in expanded:
            outputs["sarif"] = write_sarif(
                artifact_dir,
                inputs.findings,
                inputs.run,
                registry=self._sarif_registry,
            )

        if "markdown" in expanded:
            outputs["markdown"] = write_markdown(
                artifact_dir,
                inputs.run,
                findings=inputs.findings,
                module_results=inputs.module_results,
                score=inputs.score,
                policy=inputs.policy,
            )

        if audit_log_path is not None:
            self._write_audit_entries(audit_log_path, outputs)

        return outputs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _expand_formats(formats: Sequence[str]) -> set[str]:
        out: set[str] = set()
        for fmt in formats:
            if fmt in _FORMAT_ALIASES:
                out.update(_FORMAT_ALIASES[fmt])
                continue
            if fmt in SUPPORTED_FORMATS:
                out.add(fmt)
            # Unknown formats are silently ignored; the lifecycle owns
            # validation upstream.
        return out

    @staticmethod
    def _artifact_paths_map(expanded: set[str]) -> dict[str, str | None]:
        """Build the artifact_paths block fed into `run.json`."""

        return {
            "findings": "findings.json" if "findings" in expanded else None,
            "score": "score.json" if "score" in expanded else None,
            "junit": "junit.xml" if "junit" in expanded else None,
            "sarif": "sarif.json" if "sarif" in expanded else None,
            "report_html": None,  # Phase 15
            "report_md": "report.md" if "markdown" in expanded else None,
            "audit_log": "audit.log",
        }

    @staticmethod
    def _write_audit_entries(audit_log: Path, outputs: Mapping[str, Path]) -> None:
        now = datetime.now(UTC).isoformat()
        for fmt, path in sorted(outputs.items()):
            write_audit_entry(
                audit_log,
                {
                    "event": "artifact_emitted",
                    "format": fmt,
                    "path": str(path),
                    "ts": now,
                },
            )


# Lifecycle integration helper (kept in this module so the registry has
# only one place to import from).


def register_reporter_hook(
    registry: Any,  # engine.orchestrator.registry.ModuleRegistry (Any avoids circular import)
    *,
    sarif_registry: SarifRuleRegistry | None = None,
) -> None:
    """Register the Phase-03 Reporter on the ``GENERATE_REPORTS`` step.

    The hook reads the orchestrator's :class:`LifecycleContext`, builds
    a minimal :class:`ReportInputs` from whatever the run captured, and
    invokes :meth:`Reporter.emit`. Modules later in the build (Phase
    05+) will populate richer findings / scores; the hook degrades
    gracefully when they are absent.
    """

    # Imports here avoid a circular import: registry imports the
    # orchestrator module which imports the reporter.
    from engine.orchestrator.registry import LifecyclePhase

    reporter = Reporter(sarif_registry=sarif_registry)

    def _hook(ctx: Any) -> None:
        run = _testrun_from_ctx(ctx)
        if run is None:
            return
        inputs = ReportInputs(
            run=run,
            findings=tuple(getattr(ctx, "typed_findings", ())),
            module_results=tuple(getattr(ctx, "typed_module_results", ())),
            score=getattr(ctx, "typed_score", None),
            policy=getattr(ctx, "typed_policy", None),
            config_snapshot=ctx.config.to_dict(),
            policy_config=_policy_config_from_ctx(ctx),
        )
        formats = tuple(ctx.config.report.formats)
        reporter.emit(
            inputs,
            ctx.artifacts,
            formats,
            audit_log_path=ctx.audit_log_path,
        )

    registry.register_phase_hook(LifecyclePhase.GENERATE_REPORTS, _hook)


def _testrun_from_ctx(ctx: Any) -> TestRun | None:
    """Build a :class:`TestRun` from the lifecycle context."""

    if ctx.run_id is None or ctx.target is None:
        return None
    return TestRun(
        id=ctx.run_id,
        started_at=ctx.started_at,
        finished_at=ctx.finished_at,
        target=ctx.target,
        config_snapshot=ctx.config.to_dict(),
        modules_run=tuple(sorted({o.name for o in ctx.module_outcomes})),
        status=ctx.status,
    )


def _policy_config_from_ctx(ctx: Any) -> dict[str, Any]:
    """Extract the per-run policy block from the config snapshot."""

    policy = getattr(ctx.config, "policy", None)
    if policy is None:
        return {}
    if hasattr(policy, "to_dict"):
        return dict(policy.to_dict())
    return {}


__all__ = [
    "Reporter",
    "ReporterPlugin",
    "ReportFormat",
    "ReportInputs",
    "SUPPORTED_FORMATS",
    "register_reporter_hook",
]
