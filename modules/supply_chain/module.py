"""``SupplyChainModule`` (Phase 33, the documentation.3, ADR-0045).

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — no-op; missing optional binaries
  (``trivy`` / ``grype``) surface as a skipped container check rather
  than a module error.
- ``plan``                   — returns ``()`` (no Playwright specs).
- ``execute``                — runs the enabled checks against the
  project root, building a :class:`SupplyChainRunOutcome`.
- ``collect_evidence``       — writes per-check artifacts under
  ``<run-dir>/sbom/`` and ``<run-dir>/supply_chain/``.
- ``emit_findings``          — translates each check's typed report
  via :mod:`modules.supply_chain.findings`.
- ``emit_metrics``           — counts findings, lockfiles, advisories.
- ``summarize``              — overlays findings on a synthesized
  :class:`ModuleResult`.

All checks are defensive / read-only (CLAUDE §6, §26). The
forbidden-token guard at
``tests/security/test_no_offensive_supply_chain.py`` keeps stealth /
exploit literals out of the package source.
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

from modules.supply_chain.container import scan_container
from modules.supply_chain.findings import (
    findings_from_container,
    findings_from_freshness,
    findings_from_licenses,
    findings_from_osv,
    findings_from_postinstall,
)
from modules.supply_chain.freshness import evaluate_freshness
from modules.supply_chain.licenses import audit_licenses
from modules.supply_chain.models import (
    SbomDocument,
    SupplyChainRunOutcome,
)
from modules.supply_chain.options import SupplyChainModuleOptions
from modules.supply_chain.osv import run_osv_lookup_from_sbom
from modules.supply_chain.postinstall import evaluate_postinstall
from modules.supply_chain.rules import register_supply_chain_rules
from modules.supply_chain.sbom import build_sbom

# Register SARIF descriptors as a side-effect (mirrors security/api).
register_supply_chain_rules()


_ALL_CHECKS: tuple[str, ...] = (
    "sbom",
    "osv",
    "freshness",
    "postinstall",
    "container",
    "licenses",
)


class SupplyChainModule(SentinelModule):
    """the documentation.3 supply-chain audit wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "supply_chain"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
        *,
        project_root: Path | None = None,
    ) -> None:
        super().__init__(config, safety_decision)
        self._project_root_override = project_root
        self._last_outcome: SupplyChainRunOutcome | None = None
        self._last_sbom: SbomDocument | None = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        # Re-enforce policy at the lifecycle boundary so a module loaded
        # via direct factory still hits the policy check.
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
        run = self._last_outcome
        if run is None:
            return ()
        sc_dir = ctx.run_dir / "supply_chain"
        sc_dir.mkdir(parents=True, exist_ok=True)
        if run.osv is not None:
            _write_json(sc_dir / "vulnerabilities.json", run.osv.model_dump(mode="json"))
        if run.freshness is not None:
            _write_json(sc_dir / "freshness.json", run.freshness.model_dump(mode="json"))
        if run.postinstall is not None:
            _write_json(
                sc_dir / "postinstall_findings.json",
                run.postinstall.model_dump(mode="json"),
            )
        if run.container is not None:
            _write_json(sc_dir / "container.json", run.container.model_dump(mode="json"))
        if run.licenses is not None:
            _write_json(sc_dir / "licenses.json", run.licenses.model_dump(mode="json"))
        # SBOM index — written by build_sbom() into <run-dir>/sbom/index.json
        # already; we re-write the aggregate run outcome so callers can
        # reload the whole audit from a single file.
        _write_json(sc_dir / "index.json", run.model_dump(mode="json"))
        return ()

    def emit_findings(self, ctx: ModuleContext, outcome: RunnerOutcome) -> tuple[Finding, ...]:
        del outcome
        run = self._last_outcome
        if run is None:
            return ()
        target_base_url = str(ctx.target.base_url)
        findings: list[Finding] = []
        if run.osv is not None:
            findings.extend(
                findings_from_osv(
                    report=run.osv,
                    run_id=ctx.run_id,
                    target_base_url=target_base_url,
                    id_generator=ctx.id_generator,
                )
            )
        if run.freshness is not None:
            findings.extend(
                findings_from_freshness(
                    report=run.freshness,
                    run_id=ctx.run_id,
                    target_base_url=target_base_url,
                    id_generator=ctx.id_generator,
                )
            )
        if run.postinstall is not None:
            findings.extend(
                findings_from_postinstall(
                    report=run.postinstall,
                    run_id=ctx.run_id,
                    target_base_url=target_base_url,
                    id_generator=ctx.id_generator,
                )
            )
        if run.container is not None:
            findings.extend(
                findings_from_container(
                    report=run.container,
                    run_id=ctx.run_id,
                    target_base_url=target_base_url,
                    id_generator=ctx.id_generator,
                )
            )
        if run.licenses is not None:
            findings.extend(
                findings_from_licenses(
                    report=run.licenses,
                    run_id=ctx.run_id,
                    target_base_url=target_base_url,
                    id_generator=ctx.id_generator,
                )
            )
        return tuple(findings)

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        del ctx, outcome
        run = self._last_outcome
        if run is None:
            return {"checks": 0}
        return {
            "checks": _enabled_check_count(run),
            "components_total": run.sbom.components_count if run.sbom is not None else 0,
            "vulnerabilities_total": sum(
                len(c.advisories) for c in (run.osv.vulnerabilities if run.osv else ())
            ),
            "postinstall_issues": len(run.postinstall.issues) if run.postinstall else 0,
            "container_findings": len(run.container.findings) if run.container else 0,
            "license_unknown": sum(
                1
                for entry in (run.licenses.entries if run.licenses else ())
                if entry.verdict == "unknown"
            ),
            "license_deny": sum(
                1
                for entry in (run.licenses.entries if run.licenses else ())
                if entry.verdict == "deny"
            ),
            "duration_ms": run.duration_ms,
            "incomplete": int(run.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        run = self._last_outcome
        if run is None or _enabled_check_count(run) == 0:
            status: ModuleStatus = "skipped"
        elif run.incomplete:
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

    def _run_audit(self, ctx: ModuleContext) -> SupplyChainRunOutcome:
        started = datetime.now(UTC)
        options = _read_options(ctx)
        project_root = (options.project_root or self._project_root_override or Path.cwd()).resolve()
        enabled = _resolve_enabled_checks(self._config, options)
        audit_log_path = ctx.run_dir / "audit.log"
        write_audit_entry(
            audit_log_path,
            {
                "event": "supply_chain.start",
                "run_id": ctx.run_id,
                "enabled_checks": list(enabled),
                "project_root": str(project_root),
                "mode": self._safety.mode,
            },
        )

        sbom: SbomDocument | None = None
        if "sbom" in enabled or any(check in enabled for check in ("osv", "freshness", "licenses")):
            sbom_dir = ctx.run_dir / "sbom"
            sbom = build_sbom(
                project_root=project_root,
                project_name=self._config.project.name,
                sbom_dir=sbom_dir,
                now=started,
            )

        osv_report = None
        if sbom is not None and "osv" in enabled:
            sc_cfg = self._config.policy.supply_chain
            osv_report = run_osv_lookup_from_sbom(
                sbom=sbom,
                api_base=sc_cfg.osv.api_base,
                rate_limit_rps=sc_cfg.osv.rate_limit_rps,
                enabled=sc_cfg.osv.enabled,
                now=started,
            )

        freshness_report = None
        if "freshness" in enabled:
            freshness_report = evaluate_freshness(
                project_root=project_root,
                threshold_days=self._config.policy.supply_chain.max_lockfile_age_days,
                now=started,
            )

        postinstall_report = None
        if "postinstall" in enabled:
            postinstall_report = evaluate_postinstall(project_root=project_root)

        container_report = None
        if "container" in enabled:
            cfg_container = self._config.policy.supply_chain.container
            image = options.container_image or cfg_container.image
            container_report = scan_container(
                image=image,
                max_findings=cfg_container.max_findings,
            )

        license_report = None
        if sbom is not None and "licenses" in enabled:
            licenses_cfg = self._config.policy.supply_chain.licenses
            license_report = audit_licenses(
                sbom=sbom,
                allow=licenses_cfg.allow,
                deny=licenses_cfg.deny,
                unknown_severity=licenses_cfg.unknown_severity,
                now=started,
            )

        finished = datetime.now(UTC)
        duration_ms = max(0, int((finished - started).total_seconds() * 1000))
        incomplete = False
        if (
            osv_report is not None
            and osv_report.skipped
            and osv_report.skipped_reason
            and "OSV unreachable" in osv_report.skipped_reason
        ):
            # Offline OSV is incomplete (not an error, not a pass).
            incomplete = True
        outcome = SupplyChainRunOutcome(
            sbom=sbom,
            osv=osv_report,
            freshness=freshness_report,
            postinstall=postinstall_report,
            container=container_report,
            licenses=license_report,
            duration_ms=duration_ms,
            incomplete=incomplete,
        )
        write_audit_entry(
            audit_log_path,
            {
                "event": "supply_chain.end",
                "run_id": ctx.run_id,
                "duration_ms": duration_ms,
                "incomplete": incomplete,
            },
        )
        return outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_options(ctx: ModuleContext) -> SupplyChainModuleOptions:
    options = ctx.options or {}
    if isinstance(options, SupplyChainModuleOptions):
        return options
    return SupplyChainModuleOptions(
        project_root=options.get("project_root"),
        sbom_input_path=options.get("sbom_input_path"),
        enabled_checks=tuple(options.get("enabled_checks", ()) or ()),
        container_image=options.get("container_image"),
        extra_env={k: v for k, v in (options.get("extra_env") or {}).items()},
    )


def _resolve_enabled_checks(
    config: RootConfig,
    options: SupplyChainModuleOptions,
) -> tuple[str, ...]:
    """Resolve the final set of checks to run for this invocation.

    Precedence: CLI override (``options.enabled_checks``) ∩ config
    flags. Empty CLI override ⇒ honour every check enabled in config.
    """

    sc = config.policy.supply_chain
    config_enabled: list[str] = []
    if sc.sbom.enabled:
        config_enabled.append("sbom")
    if sc.osv.enabled:
        config_enabled.append("osv")
    if sc.freshness.enabled:
        config_enabled.append("freshness")
    if sc.postinstall.enabled:
        config_enabled.append("postinstall")
    if sc.container.enabled:
        config_enabled.append("container")
    if sc.licenses.enabled:
        config_enabled.append("licenses")
    if not options.enabled_checks:
        return tuple(config_enabled)
    overlap = [c for c in options.enabled_checks if c in config_enabled and c in _ALL_CHECKS]
    return tuple(overlap)


def _enabled_check_count(run: SupplyChainRunOutcome) -> int:
    return sum(
        1
        for field in (
            run.sbom,
            run.osv,
            run.freshness,
            run.postinstall,
            run.container,
            run.licenses,
        )
        if field is not None
    )


def _synthetic_runner_outcome(
    ctx: ModuleContext,
    run: SupplyChainRunOutcome,
) -> RunnerOutcome:
    """Build a stub :class:`RunnerOutcome` so the lifecycle stays uniform.

    No Playwright specs run for this module; the orchestrator still wants
    a :class:`RunnerOutcome` to thread through ``emit_findings`` /
    ``summarize``. Mirrors :func:`modules.security.module._synthetic_runner_outcome`.
    """

    if _enabled_check_count(run) == 0:
        status: ModuleStatus = "skipped"
    elif run.incomplete:
        status = "incomplete"
    else:
        status = "passed"
    return RunnerOutcome.build(
        module_name="supply_chain",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=run.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> SupplyChainModule:
    return SupplyChainModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "supply_chain" in reg.modules:
        return
    reg.register_module("supply_chain", _factory)


__all__ = [
    "SupplyChainModule",
    "SupplyChainModuleOptions",
    "_factory",
    "register_with_default_registry",
]
