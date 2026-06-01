"""``ComplianceModule`` (, the documentation.1, ADR-0046).

Lifecycle:

- ``validate_prerequisites`` — re-enforces the safety policy boundary.
- ``plan`` — returns ```` (no Playwright specs).
- ``execute`` — loads signals + audit log, runs every
 enabled sub-check (GDPR, CCPA, SOC 2), packages the result.
- ``collect_evidence`` — writes per-check summaries under
 ``<run-dir>/compliance/``.
- ``emit_findings`` — translates check reports via
 :mod:`modules.compliance.findings`.
- ``emit_metrics`` — counts checks run + per-check findings.
- ``summarize`` — overlays findings on a synthesized
 :class:`ModuleResult` (no Playwright tests).

The compliance module reads optional signals from
``<run-dir>/compliance/signals/{gdpr,ccpa}.json``. Missing signals → the
relevant sub-check reports ``skipped``; the engineering guidelines(no fake
findings, no fake passes).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
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

from modules.compliance.ccpa import run_ccpa_checks
from modules.compliance.findings import findings_from_reports
from modules.compliance.gdpr import run_gdpr_checks
from modules.compliance.inputs import load_ccpa_signals, load_gdpr_signals
from modules.compliance.models import (
    COMPLIANCE_SCHEMA_VERSION,
    CcpaCheckReport,
    GdprCheckReport,
    Soc2CheckReport,
    Wcag22CheckReport,
)
from modules.compliance.options import ComplianceModuleOptions
from modules.compliance.soc2_trail import (
    Soc2TrailInputs,
    audit_soc2_trail,
)
from modules.compliance.wcag22_check import run_wcag22_check

_ALL_CHECKS: tuple[str, ...] = ("gdpr", "ccpa", "soc2_trail", "wcag22")


class ComplianceModule(SentinelModule):
    """the documentation.1 compliance packs wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "compliance"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        super().__init__(config, safety_decision)
        self._gdpr_report: GdprCheckReport | None = None
        self._ccpa_report: CcpaCheckReport | None = None
        self._soc2_report: Soc2CheckReport | None = None
        self._wcag22_report: Wcag22CheckReport | None = None
        self._enabled: tuple[str, ...] = ()
        self._duration_ms: int = 0

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        SafetyPolicy().enforce(ctx.target, self._safety.mode)

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        del specs
        started = datetime.now(UTC)
        options = _read_options(ctx)
        enabled = _resolve_enabled_checks(options)
        self._enabled = enabled

        audit_log_path = ctx.run_dir / "audit.log"
        write_audit_entry(
            audit_log_path,
            {
                "event": "compliance.start",
                "run_id": ctx.run_id,
                "enabled_checks": list(enabled),
                "mode": self._safety.mode,
            },
        )

        signals_root = options.signals_root or (ctx.run_dir / "compliance" / "signals")

        if "gdpr" in enabled:
            gdpr_signals = load_gdpr_signals(signals_root / "gdpr.json")
            if gdpr_signals:
                self._gdpr_report = run_gdpr_checks(
                    gdpr_signals,
                    flag_missing_banner=options.flag_missing_consent_banner,
                )

        if "ccpa" in enabled:
            ccpa_signals = load_ccpa_signals(signals_root / "ccpa.json")
            if ccpa_signals:
                self._ccpa_report = run_ccpa_checks(
                    ccpa_signals,
                    enforce_link_presence=options.enforce_ccpa_link_presence,
                )

        if "soc2_trail" in enabled:
            trail_path = options.audit_log_path or audit_log_path
            self._soc2_report = audit_soc2_trail(
                trail_path,
                inputs=Soc2TrailInputs(
                    require_llm_events=options.require_llm_events,
                    require_vault_events=options.require_vault_events,
                    expected_modules=options.expected_modules,
                ),
            )

        if "wcag22" in enabled:
            wcag_signals = signals_root / "wcag22.json"
            wcag_report = run_wcag22_check(wcag_signals)
            if wcag_report.signals_seen:
                self._wcag22_report = wcag_report

        finished = datetime.now(UTC)
        self._duration_ms = max(0, int((finished - started).total_seconds() * 1000))

        write_audit_entry(
            audit_log_path,
            {
                "event": "compliance.end",
                "run_id": ctx.run_id,
                "duration_ms": self._duration_ms,
            },
        )
        return _synthetic_runner_outcome(ctx, self)

    def collect_evidence(self, ctx: ModuleContext, outcome: RunnerOutcome) -> tuple[Evidence, ...]:
        del outcome
        comp_dir = ctx.run_dir / "compliance"
        comp_dir.mkdir(parents=True, exist_ok=True)
        if self._gdpr_report is not None:
            _write_json(comp_dir / "gdpr.json", self._gdpr_report.model_dump(mode="json"))
        if self._ccpa_report is not None:
            _write_json(comp_dir / "ccpa.json", self._ccpa_report.model_dump(mode="json"))
        if self._soc2_report is not None:
            _write_json(
                comp_dir / "soc2_trail.json",
                self._soc2_report.model_dump(mode="json"),
            )
        if self._wcag22_report is not None:
            _write_json(
                comp_dir / "wcag22.json",
                self._wcag22_report.model_dump(mode="json"),
            )
        _write_json(
            comp_dir / "index.json",
            {
                "schema_version": COMPLIANCE_SCHEMA_VERSION,
                "enabled_checks": list(self._enabled),
                "gdpr_ran": self._gdpr_report is not None,
                "ccpa_ran": self._ccpa_report is not None,
                "soc2_ran": self._soc2_report is not None,
                "wcag22_ran": self._wcag22_report is not None,
                "duration_ms": self._duration_ms,
            },
        )
        return ()

    def emit_findings(self, ctx: ModuleContext, outcome: RunnerOutcome) -> tuple[Finding, ...]:
        del outcome
        return findings_from_reports(
            gdpr=self._gdpr_report,
            ccpa=self._ccpa_report,
            soc2=self._soc2_report,
            wcag22=self._wcag22_report,
            run_id=ctx.run_id,
            target_base_url=str(ctx.target.base_url),
            id_generator=ctx.id_generator,
            artifact_paths={
                "gdpr": "compliance/gdpr.json",
                "ccpa": "compliance/ccpa.json",
                "soc2": "compliance/soc2_trail.json",
                "wcag22": "compliance/wcag22.json",
            },
        )

    def emit_metrics(self, ctx: ModuleContext, outcome: RunnerOutcome) -> Mapping[str, float | int]:
        del ctx, outcome
        return {
            "checks_run": _checks_run_count(self),
            "gdpr_findings": (
                len(self._gdpr_report.issues) if self._gdpr_report is not None else 0
            ),
            "ccpa_findings": (
                len(self._ccpa_report.issues) if self._ccpa_report is not None else 0
            ),
            "soc2_findings": (
                len(self._soc2_report.issues) if self._soc2_report is not None else 0
            ),
            "wcag22_findings": (
                len(self._wcag22_report.issues) if self._wcag22_report is not None else 0
            ),
            "duration_ms": self._duration_ms,
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        del ctx
        if _checks_run_count(self) == 0:
            status: ModuleStatus = "skipped"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_options(ctx: ModuleContext) -> ComplianceModuleOptions:
    options = ctx.options or {}
    if isinstance(options, ComplianceModuleOptions):
        return options
    return ComplianceModuleOptions(
        enabled_checks=tuple(options.get("enabled_checks", ()) or ()),
        signals_root=options.get("signals_root"),
        audit_log_path=options.get("audit_log_path"),
        flag_missing_consent_banner=bool(options.get("flag_missing_consent_banner", False)),
        enforce_ccpa_link_presence=bool(options.get("enforce_ccpa_link_presence", True)),
        require_llm_events=bool(options.get("require_llm_events", False)),
        require_vault_events=bool(options.get("require_vault_events", False)),
        expected_modules=tuple(options.get("expected_modules", ()) or ()),
        extra_env={k: v for k, v in (options.get("extra_env") or {}).items()},
    )


def _resolve_enabled_checks(options: ComplianceModuleOptions) -> tuple[str, ...]:
    if not options.enabled_checks:
        return _ALL_CHECKS
    overlap = [c for c in options.enabled_checks if c in _ALL_CHECKS]
    return tuple(overlap)


def _checks_run_count(module: ComplianceModule) -> int:
    return sum(
        1
        for report in (
            module._gdpr_report,
            module._ccpa_report,
            module._soc2_report,
            module._wcag22_report,
        )
        if report is not None
    )


def _synthetic_runner_outcome(ctx: ModuleContext, module: ComplianceModule) -> RunnerOutcome:
    if _checks_run_count(module) == 0:
        status: ModuleStatus = "skipped"
    else:
        status = "passed"
    return RunnerOutcome.build(
        module_name="compliance",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=module._duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> ComplianceModule:
    return ComplianceModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "compliance" in reg.modules:
        return
    reg.register_module("compliance", _factory)


__all__ = [
    "COMPLIANCE_SCHEMA_VERSION",
    "ComplianceModule",
    "ComplianceModuleOptions",
    "_factory",
    "register_with_default_registry",
]
