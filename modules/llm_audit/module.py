"""``LlmAuditModule`` (, the documentation, ADR-0024).

Lifecycle:

- ``validate_prerequisites`` — no-op; missing signals simply skip the
 corresponding check (the engineering guidelines— no fake completion, but no over-
 reporting either).
- ``plan`` — reads :class:`LlmAuditModuleOptions`
 off ``ctx.options``, locates discovery + signal artifacts.
- ``execute`` — loads inputs, runs each enabled check,
 collects :class:`CheckFinding` records.
- ``emit_findings`` — translates them into typed
 :class:`Finding` records via
 :func:`modules.llm_audit.findings.findings_from_check_findings`.
- ``emit_metrics`` — per-rule counts + ``checks_run``.
- ``summarize`` — overlays findings on a synthesized
 :class:`RunnerOutcome` (no Playwright tests).

The module persists ``<run-dir>/llm_audit/index.json`` listing every
check that ran, how many findings each produced, and the set of
signals that were available.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from engine.config.schema import RootConfig
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.safety import SafetyDecision
from engine.runner.results import EnvironmentContext, RunnerOutcome

from modules.llm_audit.checks.coming_soon import check_coming_soon
from modules.llm_audit.checks.console_errors import check_console_errors
from modules.llm_audit.checks.dead_buttons import check_dead_buttons
from modules.llm_audit.checks.fake_routes import check_fake_endpoints, check_fake_routes
from modules.llm_audit.checks.forms_no_submit import check_forms_no_submit
from modules.llm_audit.checks.hardcoded_creds import check_hardcoded_credentials
from modules.llm_audit.checks.incomplete_crud import check_incomplete_crud
from modules.llm_audit.checks.loading_error_states import check_loading_error_states
from modules.llm_audit.checks.localstorage_secrets import check_localstorage_secrets
from modules.llm_audit.checks.mock_data import (
    check_mock_data_in_bundles,
    check_mock_data_in_rendered_text,
)
from modules.llm_audit.checks.ui_only_auth import check_ui_only_auth
from modules.llm_audit.checks.validation_mismatch import check_validation_mismatch
from modules.llm_audit.findings import CheckFinding, findings_from_check_findings
from modules.llm_audit.inputs import load_inputs
from modules.llm_audit.models import LlmAuditInputs
from modules.llm_audit.options import LlmAuditModuleOptions

# Canonical check identifiers users can pass on the CLI / SDK.
ALL_CHECKS: tuple[str, ...] = (
    "dead_buttons",
    "fake_routes",
    "fake_endpoints",
    "mock_data",
    "forms_no_submit",
    "incomplete_crud",
    "ui_only_auth",
    "hardcoded_creds",
    "localstorage_secrets",
    "loading_error_states",
    "validation_mismatch",
    "coming_soon",
    "console_errors",
)


@dataclass(frozen=True)
class _CheckOutcome:
    """Internal record per executed check."""

    name: str
    findings: tuple[CheckFinding, ...]
    signal_available: bool


class LlmAuditModule(SentinelModule):
    """LLM-Code audit module — / the documentation."""

    name: ClassVar[str] = "llm_audit"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        super().__init__(config, safety_decision)
        self._last_inputs: LlmAuditInputs | None = None
        self._last_outcomes: tuple[_CheckOutcome, ...] = ()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        return

    def plan(self, ctx: ModuleContext) -> Sequence[Path]:
        # The module does not drive Playwright; the base's spec-walk
        # signature is satisfied with an empty tuple. Real check
        # planning happens inside ``execute``.
        del ctx
        return ()

    def execute(self, ctx: ModuleContext, specs: Sequence[Path]) -> RunnerOutcome:
        del specs
        options = _read_options(ctx)
        inputs = load_inputs(
            discovery_path=options.discovery_path,
            signals_root=options.signals_root,
            third_party_console_hosts=options.third_party_console_hosts,
        )
        self._last_inputs = inputs
        enabled = _enabled_checks(options.checks)
        outcomes = self._run_checks(inputs, enabled)
        self._last_outcomes = outcomes
        _persist_index(ctx.run_dir, outcomes, enabled)
        return _synthetic_runner_outcome(ctx, outcomes)

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        check_findings: list[CheckFinding] = []
        for record in self._last_outcomes:
            check_findings.extend(record.findings)
        return findings_from_check_findings(
            check_findings,
            run_id=ctx.run_id,
            module_name=self.name,
            target_base_url=str(ctx.target.base_url),
            id_generator=ctx.id_generator,
            artifact_root=ctx.run_dir,
        )

    def emit_metrics(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> Mapping[str, float | int]:
        del ctx, outcome
        per_check: dict[str, float | int] = {}
        total_findings = 0
        for record in self._last_outcomes:
            per_check[f"findings_{record.name}"] = len(record.findings)
            total_findings += len(record.findings)
        per_check["checks_run"] = sum(
            1 for record in self._last_outcomes if record.signal_available
        )
        per_check["checks_skipped"] = sum(
            1 for record in self._last_outcomes if not record.signal_available
        )
        per_check["findings_total"] = total_findings
        return per_check

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        # Mirror the a11y / perf pattern: status reflects whether the
        # module had any signal AND whether it produced blocking
        # findings. ``skipped`` only when no signal was available at all.
        if all(not record.signal_available for record in self._last_outcomes):
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_checks(
        self,
        inputs: LlmAuditInputs,
        enabled: frozenset[str],
    ) -> tuple[_CheckOutcome, ...]:
        results: list[_CheckOutcome] = []
        if "dead_buttons" in enabled:
            results.append(
                _CheckOutcome(
                    name="dead_buttons",
                    findings=check_dead_buttons(inputs.buttons),
                    signal_available=bool(inputs.buttons),
                )
            )
        if "fake_routes" in enabled:
            results.append(
                _CheckOutcome(
                    name="fake_routes",
                    findings=check_fake_routes(
                        inputs.link_references,
                        observed_routes=inputs.observed_routes,
                        observed_route_status=inputs.observed_route_status,
                    ),
                    signal_available=bool(inputs.link_references),
                )
            )
        if "fake_endpoints" in enabled:
            results.append(
                _CheckOutcome(
                    name="fake_endpoints",
                    findings=check_fake_endpoints(
                        inputs.api_references,
                        observed_endpoints=inputs.observed_endpoints,
                        openapi_endpoints=inputs.openapi_endpoints,
                    ),
                    signal_available=bool(inputs.api_references),
                )
            )
        if "mock_data" in enabled:
            bundle_findings = check_mock_data_in_bundles(inputs.bundles)
            text_findings = check_mock_data_in_rendered_text(inputs.rendered_text)
            results.append(
                _CheckOutcome(
                    name="mock_data",
                    findings=tuple(bundle_findings) + tuple(text_findings),
                    signal_available=bool(inputs.bundles or inputs.rendered_text),
                )
            )
        if "forms_no_submit" in enabled:
            results.append(
                _CheckOutcome(
                    name="forms_no_submit",
                    findings=check_forms_no_submit(inputs.forms),
                    signal_available=bool(inputs.forms),
                )
            )
        if "incomplete_crud" in enabled:
            results.append(
                _CheckOutcome(
                    name="incomplete_crud",
                    findings=check_incomplete_crud(inputs.resources),
                    signal_available=bool(inputs.resources),
                )
            )
        if "ui_only_auth" in enabled:
            results.append(
                _CheckOutcome(
                    name="ui_only_auth",
                    findings=check_ui_only_auth(inputs.auth_route_probes),
                    signal_available=bool(inputs.auth_route_probes),
                )
            )
        if "hardcoded_creds" in enabled:
            results.append(
                _CheckOutcome(
                    name="hardcoded_creds",
                    findings=check_hardcoded_credentials(inputs.source_files),
                    signal_available=bool(inputs.source_files),
                )
            )
        if "localstorage_secrets" in enabled:
            results.append(
                _CheckOutcome(
                    name="localstorage_secrets",
                    findings=check_localstorage_secrets(inputs.storage_samples),
                    signal_available=bool(inputs.storage_samples),
                )
            )
        if "loading_error_states" in enabled:
            results.append(
                _CheckOutcome(
                    name="loading_error_states",
                    findings=check_loading_error_states(inputs.loading_error_observations),
                    signal_available=bool(inputs.loading_error_observations),
                )
            )
        if "validation_mismatch" in enabled:
            results.append(
                _CheckOutcome(
                    name="validation_mismatch",
                    findings=check_validation_mismatch(inputs.validation_probes),
                    signal_available=bool(inputs.validation_probes),
                )
            )
        if "coming_soon" in enabled:
            results.append(
                _CheckOutcome(
                    name="coming_soon",
                    findings=check_coming_soon(inputs.rendered_text),
                    signal_available=bool(inputs.rendered_text),
                )
            )
        if "console_errors" in enabled:
            results.append(
                _CheckOutcome(
                    name="console_errors",
                    findings=check_console_errors(
                        inputs.console_entries,
                        third_party_hosts=inputs.third_party_console_hosts,
                    ),
                    signal_available=bool(inputs.console_entries),
                )
            )
        return tuple(results)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> LlmAuditModuleOptions:
    raw: Any = ctx.options.get("llm_audit") if "llm_audit" in ctx.options else ctx.options
    if isinstance(raw, LlmAuditModuleOptions):
        return raw
    if isinstance(raw, Mapping):
        discovery_value = raw.get("discovery_path")
        if discovery_value is None:
            discovery_path: Path | None = None
        elif isinstance(discovery_value, Path):
            discovery_path = discovery_value
        else:
            discovery_path = Path(str(discovery_value))
        signals_value = raw.get("signals_root")
        if signals_value is None:
            signals_root: Path | None = None
        elif isinstance(signals_value, Path):
            signals_root = signals_value
        else:
            signals_root = Path(str(signals_value))
        checks_value = raw.get("checks") or ()
        if isinstance(checks_value, str):
            checks = tuple(c.strip() for c in checks_value.split(",") if c.strip())
        else:
            checks = tuple(str(c) for c in checks_value)
        third_party_value = raw.get("third_party_console_hosts") or ()
        if isinstance(third_party_value, str):
            third_party = tuple(
                host.strip() for host in third_party_value.split(",") if host.strip()
            )
        else:
            third_party = tuple(str(host) for host in third_party_value)
        return LlmAuditModuleOptions(
            discovery_path=discovery_path,
            signals_root=signals_root,
            checks=checks,
            third_party_console_hosts=third_party,
            extra_env=raw.get("extra_env", {}),
        )
    return LlmAuditModuleOptions()


def _enabled_checks(requested: tuple[str, ...]) -> frozenset[str]:
    if not requested:
        return frozenset(ALL_CHECKS)
    invalid = tuple(name for name in requested if name not in ALL_CHECKS)
    if invalid:
        raise ValueError(
            "Unknown LLM-audit check(s): "
            f"{', '.join(sorted(invalid))!r}. "
            f"Allowed: {', '.join(ALL_CHECKS)}."
        )
    return frozenset(requested)


def _synthetic_runner_outcome(
    ctx: ModuleContext,
    outcomes: tuple[_CheckOutcome, ...],
) -> RunnerOutcome:
    has_any_signal = any(record.signal_available for record in outcomes)
    status: ModuleStatus = "passed" if has_any_signal else "skipped"
    return RunnerOutcome.build(
        module_name="llm_audit",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="n/a",
            os="unknown",
        ),
    )


def _persist_index(
    run_dir: Path,
    outcomes: tuple[_CheckOutcome, ...],
    enabled: frozenset[str],
) -> None:
    """Write ``<run-dir>/llm_audit/index.json`` summarising the audit."""

    target = run_dir / "llm_audit"
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1",
        "checks": [
            {
                "name": record.name,
                "enabled": record.name in enabled,
                "signal_available": record.signal_available,
                "findings": len(record.findings),
            }
            for record in outcomes
        ],
    }
    index_path = target / "index.json"
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    index_path.write_text(text, encoding="utf-8")


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> LlmAuditModule:
    return LlmAuditModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "llm_audit" in reg.modules:
        return
    reg.register_module("llm_audit", _factory)


__all__ = [
    "ALL_CHECKS",
    "LlmAuditModule",
    "LlmAuditModuleOptions",
    "_factory",
    "register_with_default_registry",
]
