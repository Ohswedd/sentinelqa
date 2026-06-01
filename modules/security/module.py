"""``SecurityModule`` (, the documentation, ADR-0018).

Lifecycle (CLAUDE §9):

- ``validate_prerequisites`` — no-op; missing optional binaries
 (``pip-audit`` / ``semgrep``) are surfaced by ``sentinel doctor``,
 not as a module error.
- ``plan`` — resolves the route list (CLI options
 → discovery.json → config.security.routes → ``("/",)`` fallback
 only when the CLI explicitly injects it).
- ``execute`` — drives each enabled check through
 :func:`SafetyPolicy.enforce` first; collects results into a
 :class:`SecurityRunOutcome`.
- ``collect_evidence`` — writes ``security/<check>.json`` and
 ``security/index.json``.
- ``emit_findings`` — translates each :class:`SecurityIssue`
 via :func:`modules.security.findings.findings_from_checks`.
- ``emit_metrics`` — counts issues per check, total
 targets scanned, total duration.
- ``summarize`` — overlays findings on a synthesized
 :class:`ModuleResult` (no Playwright tests run; no
 :class:`RunnerOutcome` exists).

Every public method begins with :func:`SafetyPolicy.enforce` (or
delegates to a check that does); the AST guard in
``tests/security/test_module_calls_policy.py`` enforces this.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
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

from modules.security.checks.context import CheckContext
from modules.security.checks.cookies import run_cookies_check
from modules.security.checks.cors import run_cors_check
from modules.security.checks.csrf import run_csrf_check
from modules.security.checks.deps import RunCallable, run_dependency_scan
from modules.security.checks.frontend_secrets import run_frontend_secrets_check
from modules.security.checks.headers import run_headers_check
from modules.security.checks.idor import run_idor_check
from modules.security.checks.sast import run_sast
from modules.security.checks.sqli import run_sqli_check
from modules.security.checks.xss_reflected import run_xss_reflected_check
from modules.security.checks.xss_stored import run_xss_stored_check
from modules.security.findings import findings_from_checks
from modules.security.http_client import build_client
from modules.security.models import (
    SECURITY_RESULT_SCHEMA_VERSION,
    SecurityCheckResult,
    SecurityRunOutcome,
)
from modules.security.options import SecurityModuleOptions
from modules.security.rules import register_security_rules

# Register SARIF descriptors as a side-effect of importing the module.
register_security_rules()


# (check_name, runner_callable, requires_extra) — order = canonical run order.
_HTTP_CHECKS: tuple[tuple[str, Callable[[CheckContext], SecurityCheckResult]], ...] = (
    ("headers", run_headers_check),
    ("cookies", run_cookies_check),
    ("cors", run_cors_check),
    ("csrf", run_csrf_check),
    ("xss_reflected", run_xss_reflected_check),
    ("xss_stored", run_xss_stored_check),
    ("sqli", run_sqli_check),
    ("idor", run_idor_check),
)


class SecurityModule(SentinelModule):
    """the documentation safe security checks wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "security"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
        *,
        project_root: Path | None = None,
        snapshot_dir: Path | None = None,
        deps_run: RunCallable | None = None,
        sast_run: RunCallable | None = None,
    ) -> None:
        super().__init__(config, safety_decision)
        self._project_root = project_root or Path.cwd()
        self._snapshot_dir = snapshot_dir
        self._deps_run = deps_run
        self._sast_run = sast_run

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
        # Re-enforce policy at the lifecycle boundary. Re-running it is
        # cheap and means a module loaded via direct factory still gets
        # the policy check.
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
        sec_outcome: SecurityRunOutcome | None = getattr(self, "_last_outcome", None)
        if sec_outcome is None:
            return ()
        sec_dir = ctx.run_dir / "security"
        sec_dir.mkdir(parents=True, exist_ok=True)
        for check in sec_outcome.checks:
            path = sec_dir / f"{check.check}.json"
            path.write_text(
                json.dumps(check.model_dump(mode="json"), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        index_path = sec_dir / "index.json"
        index_path.write_text(
            json.dumps(sec_outcome.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return ()

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        sec_outcome: SecurityRunOutcome | None = getattr(self, "_last_outcome", None)
        if sec_outcome is None:
            return ()
        artifact_paths = {
            check.check: f"security/{check.check}.json" for check in sec_outcome.checks
        }
        return findings_from_checks(
            checks=sec_outcome.checks,
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
        sec_outcome: SecurityRunOutcome | None = getattr(self, "_last_outcome", None)
        if sec_outcome is None:
            return {"checks": 0}
        total_issues = sum(len(c.issues) for c in sec_outcome.checks)
        targets = sum(c.targets_scanned for c in sec_outcome.checks)
        skipped = sum(1 for c in sec_outcome.checks if c.skipped)
        return {
            "checks": len(sec_outcome.checks),
            "checks_skipped": skipped,
            "issues_total": total_issues,
            "targets_scanned": targets,
            "duration_ms": sec_outcome.duration_ms,
            "incomplete": int(sec_outcome.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        sec_outcome: SecurityRunOutcome | None = getattr(self, "_last_outcome", None)
        if sec_outcome is None or (
            not sec_outcome.checks or all(c.skipped for c in sec_outcome.checks)
        ):
            status: ModuleStatus = "skipped"
        elif sec_outcome.incomplete:
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

    def _run_audit(self, ctx: ModuleContext) -> SecurityRunOutcome:
        options = _read_options(ctx)
        routes = _resolve_routes(self._config, options)
        enabled = _resolve_enabled_checks(self._config, options)
        audit_log_path = ctx.run_dir / "audit.log"
        write_audit_entry(
            audit_log_path,
            {
                "event": "security.start",
                "run_id": ctx.run_id,
                "enabled_checks": list(enabled),
                "routes": list(routes),
                "mode": self._safety.mode,
            },
        )
        if not routes:
            write_audit_entry(
                audit_log_path,
                {
                    "event": "security.no_routes",
                    "run_id": ctx.run_id,
                },
            )
            return SecurityRunOutcome(
                schema_version=SECURITY_RESULT_SCHEMA_VERSION,
                checks=(),
                duration_ms=0,
                incomplete=False,
            )

        with build_client(
            base_url=str(ctx.target.base_url),
            run_id=ctx.run_id,
            timeout_seconds=self._config.security.request_timeout_seconds,
        ) as client:
            check_ctx = CheckContext(
                run_id=ctx.run_id,
                target=ctx.target,
                routes=routes,
                config=self._config,
                safety=self._safety,
                client=client,
                audit_log_path=audit_log_path,
                env=dict(os.environ),
            )
            results: list[SecurityCheckResult] = []
            for name, runner in _HTTP_CHECKS:
                if name not in enabled:
                    continue
                results.append(runner(check_ctx))
            if "frontend_secrets" in enabled:
                results.append(
                    run_frontend_secrets_check(check_ctx, snapshot_dir=self._snapshot_dir)
                )

            if "dependency_scan" in enabled:
                results.append(
                    run_dependency_scan(
                        check_ctx,
                        project_root=self._project_root,
                        run=self._deps_run,
                    )
                )
            if "sast" in enabled:
                results.append(
                    run_sast(
                        check_ctx,
                        project_root=self._project_root,
                        run=self._sast_run,
                    )
                )
        total_duration = sum(r.duration_ms for r in results)
        write_audit_entry(
            audit_log_path,
            {
                "event": "security.complete",
                "run_id": ctx.run_id,
                "checks_executed": [r.check for r in results],
                "issues": sum(len(r.issues) for r in results),
            },
        )
        return SecurityRunOutcome(
            schema_version=SECURITY_RESULT_SCHEMA_VERSION,
            checks=tuple(results),
            duration_ms=total_duration,
            incomplete=False,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> SecurityModuleOptions:
    raw = ctx.options.get("security") if "security" in ctx.options else ctx.options
    if isinstance(raw, SecurityModuleOptions):
        return raw
    if isinstance(raw, dict):
        routes_value: Any = raw.get("routes") or ()
        if isinstance(routes_value, str):
            routes_tuple: tuple[str, ...] = (routes_value,)
        else:
            routes_tuple = tuple(str(r) for r in routes_value)
        discovery_value: Any = raw.get("discovery_path")
        if discovery_value is None:
            discovery_path: Path | None = None
        elif isinstance(discovery_value, Path):
            discovery_path = discovery_value
        else:
            discovery_path = Path(str(discovery_value))
        enabled_value: Any = raw.get("enabled_checks") or ()
        enabled_tuple = tuple(str(c) for c in enabled_value)
        return SecurityModuleOptions(
            routes=routes_tuple,
            discovery_path=discovery_path,
            enabled_checks=enabled_tuple,
            extra_env=raw.get("extra_env", {}),
        )
    return SecurityModuleOptions()


def _routes_from_discovery(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    candidates: list[str] = []
    routes = payload.get("routes") if isinstance(payload, dict) else None
    if isinstance(routes, list):
        for entry in routes:
            if isinstance(entry, dict):
                value = entry.get("path") or entry.get("route")
                if isinstance(value, str) and value:
                    candidates.append(value)
            elif isinstance(entry, str):
                candidates.append(entry)
    seen: set[str] = set()
    out: list[str] = []
    for r in candidates:
        norm = _normalize_route(r)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return tuple(out)


def _normalize_route(route: str) -> str:
    cleaned = route.strip()
    if not cleaned:
        return "/"
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    if cleaned.startswith("/"):
        return cleaned
    return "/" + cleaned


def _resolve_routes(
    config: RootConfig,
    options: SecurityModuleOptions,
) -> tuple[str, ...]:
    if options.routes:
        return tuple(_normalize_route(r) for r in options.routes)
    if options.discovery_path is not None:
        routes = _routes_from_discovery(options.discovery_path)
        if routes:
            return routes
    if config.security.routes:
        return tuple(_normalize_route(r) for r in config.security.routes)
    return ()


def _resolve_enabled_checks(
    config: RootConfig,
    options: SecurityModuleOptions,
) -> tuple[str, ...]:
    """Return the canonical (config-ordered) set of enabled checks.

    ``options.enabled_checks``, when non-empty, restricts the set to
    the named checks AND still respects the config booleans (so a CLI
    user cannot turn on a check that is config-OFF without also
    flipping the config).
    """

    cfg = config.security.checks
    canonical = (
        ("headers", cfg.headers),
        ("cookies", cfg.cookies),
        ("cors", cfg.cors),
        ("csrf", cfg.csrf),
        ("xss_reflected", cfg.xss_reflected),
        ("xss_stored", cfg.xss_stored),
        ("sqli", cfg.sqli),
        ("idor", cfg.idor),
        ("frontend_secrets", cfg.frontend_secrets),
        ("dependency_scan", cfg.dependency_scan),
        ("sast", cfg.sast),
    )
    config_enabled = tuple(name for name, on in canonical if on)
    if options.enabled_checks:
        restriction = set(options.enabled_checks)
        return tuple(name for name in config_enabled if name in restriction)
    return config_enabled


def _route_slug(route: str) -> str:
    if route in {"", "/"}:
        return "root"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", route).strip("-")
    return base or "root"


def _synthetic_runner_outcome(ctx: ModuleContext, sec_outcome: SecurityRunOutcome) -> RunnerOutcome:
    status: ModuleStatus = (
        "skipped"
        if not sec_outcome.checks or all(c.skipped for c in sec_outcome.checks)
        else ("incomplete" if sec_outcome.incomplete else "passed")
    )
    return RunnerOutcome.build(
        module_name="security",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=sec_outcome.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> SecurityModule:
    return SecurityModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "security" in reg.modules:
        return
    reg.register_module("security", _factory)


_ = datetime.now(UTC)  # keep zoneinfo import live for ruff/mypy


__all__ = [
    "SecurityModule",
    "SecurityModuleOptions",
    "_factory",
    "register_with_default_registry",
]
