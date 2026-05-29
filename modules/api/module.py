"""``ApiModule`` (Phase 22, PRD §10.3, CLAUDE.md §30, ADR-0020).

Lifecycle (CLAUDE.md §9):

- ``validate_prerequisites`` — re-enforces :class:`SafetyPolicy` so the
  module fails closed if the orchestrator wasn't called through the
  CLI / SDK happy path.
- ``plan``                   — no specs (the module is HTTP-driven, not
  Playwright-driven).
- ``execute``                — dispatches to each enabled check
  (``contract`` / ``negative`` / ``auth`` / ``latency`` / ``pagination`` /
  ``error_shape`` / ``backward_compat``). Each check is responsible
  for its own SafetyPolicy.enforce hop before issuing HTTP.
- ``collect_evidence``       — writes ``api/<check>.json`` per check
  plus ``api/index.json`` and (when an OpenAPI / GraphQL doc was
  loaded) ``api/api-schema.json`` for backward-compat diff in future
  runs.
- ``emit_findings``          — translates each :class:`ApiIssue` via
  :func:`modules.api.findings.findings_from_checks`.
- ``emit_metrics``           — counts per-check issues + per-check
  scanned targets + total duration.
- ``summarize``              — overlays findings on a synthesized
  :class:`RunnerOutcome` (no Playwright tests run).

Safety boundary (CLAUDE.md §30): aggressive fuzzing is forbidden. No
field, option, env var, or CLI flag named ``aggressive`` / ``fuzz`` /
``brute`` / ``stress`` exists in this module. The body-size cap in
:func:`modules.api.http_client.safe_request` is the I/O-layer
backstop. The ``tests/security/test_api_no_aggressive_flags.py``
guard greps the package + the CLI for forbidden literals.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, ClassVar

import httpx
from engine.config.schema import RootConfig
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding
from engine.domain.module_result import ModuleResult, ModuleStatus
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry, default_registry
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyDecision, SafetyPolicy
from engine.runner.results import EnvironmentContext, RunnerOutcome

from modules.api.backward_compat import (
    diff_snapshots,
    load_previous_snapshot,
    write_snapshot,
)
from modules.api.checks.auth import run_auth_check
from modules.api.checks.contract_graphql import run_graphql_contract_check
from modules.api.checks.contract_openapi import run_openapi_contract_check
from modules.api.checks.error_shape import run_error_shape_check
from modules.api.checks.latency import run_latency_check
from modules.api.checks.negative import run_negative_check
from modules.api.checks.pagination import run_pagination_check
from modules.api.findings import findings_from_checks
from modules.api.graphql import GraphqlSchema, load_graphql
from modules.api.http_client import build_client
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    API_SCHEMA_SNAPSHOT_VERSION,
    ApiCheckName,
    ApiCheckResult,
    ApiIssue,
    ApiRunOutcome,
    ApiSchemaSnapshot,
)
from modules.api.openapi import OpenApiDocument, load_openapi
from modules.api.options import ApiModuleOptions

# Canonical run order: contract first (it's the cheapest schema check and
# its loaded spec feeds every later check), then variants that mutate
# requests, then the read-only walkers, then backward-compat last so it
# sees the snapshot written in this run.
_RUN_ORDER: tuple[ApiCheckName, ...] = (
    "contract",
    "negative",
    "auth",
    "pagination",
    "error_shape",
    "latency",
    "backward_compat",
)


class ApiModule(SentinelModule):
    """PRD §10.3 API testing wired into the SentinelQA lifecycle."""

    name: ClassVar[str] = "api"

    def __init__(
        self,
        config: RootConfig,
        safety_decision: SafetyDecision,
    ) -> None:
        super().__init__(config, safety_decision)
        self._last_outcome: ApiRunOutcome | None = None
        self._snapshot: ApiSchemaSnapshot | None = None

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def validate_prerequisites(self, ctx: ModuleContext) -> None:
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
        api_outcome = self._last_outcome
        if api_outcome is None:
            return ()
        api_dir = ctx.run_dir / "api"
        api_dir.mkdir(parents=True, exist_ok=True)
        for check in api_outcome.checks:
            path = api_dir / f"{check.check}.json"
            path.write_text(
                json.dumps(check.model_dump(mode="json"), indent=2, sort_keys=True),
                encoding="utf-8",
            )
        index_path = api_dir / "index.json"
        index_path.write_text(
            json.dumps(api_outcome.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if self._snapshot is not None:
            write_snapshot(api_dir / "api-schema.json", self._snapshot)
        return ()

    def emit_findings(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
    ) -> tuple[Finding, ...]:
        del outcome
        api_outcome = self._last_outcome
        if api_outcome is None:
            return ()
        artifact_paths: dict[str, str] = {
            str(check.check): f"api/{check.check}.json" for check in api_outcome.checks
        }
        return findings_from_checks(
            checks=api_outcome.checks,
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
        api_outcome = self._last_outcome
        if api_outcome is None:
            return {"checks": 0}
        total_issues = sum(len(c.issues) for c in api_outcome.checks)
        targets = sum(c.targets_scanned for c in api_outcome.checks)
        skipped = sum(1 for c in api_outcome.checks if c.skipped)
        return {
            "checks": len(api_outcome.checks),
            "checks_skipped": skipped,
            "issues_total": total_issues,
            "targets_scanned": targets,
            "duration_ms": api_outcome.duration_ms,
            "openapi_loaded": int(api_outcome.openapi_loaded),
            "graphql_loaded": int(api_outcome.graphql_loaded),
            "incomplete": int(api_outcome.incomplete),
        }

    def summarize(
        self,
        ctx: ModuleContext,
        outcome: RunnerOutcome,
        findings: tuple[Finding, ...],
        metrics: Mapping[str, float | int],
    ) -> ModuleResult:
        api_outcome = self._last_outcome
        if api_outcome is None or (
            not api_outcome.checks or all(c.skipped for c in api_outcome.checks)
        ):
            status: ModuleStatus = "skipped"
        elif api_outcome.incomplete:
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

    def _run_audit(self, ctx: ModuleContext) -> ApiRunOutcome:
        options = _read_options(ctx)
        enabled = _resolve_enabled_checks(self._config, options)
        audit_log_path = ctx.run_dir / "audit.log"
        write_audit_entry(
            audit_log_path,
            {
                "event": "api.start",
                "run_id": ctx.run_id,
                "enabled_checks": list(enabled),
                "mode": self._safety.mode,
            },
        )
        started = perf_counter()
        results: list[ApiCheckResult] = []

        openapi_doc: OpenApiDocument | None = None
        graphql_schema: GraphqlSchema | None = None
        openapi_path = options.openapi_path or self._config.api.openapi_path
        graphql_path = options.graphql_path or self._config.api.graphql_path
        if openapi_path is not None and openapi_path.exists():
            try:
                openapi_doc = load_openapi(openapi_path)
            except Exception as exc:
                results.append(
                    _skip_result(
                        "contract",
                        f"failed to load OpenAPI doc at {openapi_path}: {exc}",
                    )
                )
        if graphql_path is not None and graphql_path.exists():
            try:
                graphql_schema = load_graphql(graphql_path)
            except Exception as exc:
                results.append(
                    _skip_result(
                        "contract",
                        f"failed to load GraphQL SDL at {graphql_path}: {exc}",
                    )
                )

        snapshot: ApiSchemaSnapshot | None = None
        if openapi_doc is not None:
            snapshot = ApiSchemaSnapshot(
                schema_version=API_SCHEMA_SNAPSHOT_VERSION,
                source="openapi",
                endpoints=openapi_doc.snapshot_endpoints(),
            )
        elif graphql_schema is not None:
            snapshot = ApiSchemaSnapshot(
                schema_version=API_SCHEMA_SNAPSHOT_VERSION,
                source="graphql",
                endpoints=graphql_schema.snapshot_endpoints(),
            )
        self._snapshot = snapshot

        client_ctx = build_client(
            base_url=str(ctx.target.base_url),
            run_id=ctx.run_id,
            timeout_seconds=self._config.api.request_timeout_seconds,
        )
        try:
            with client_ctx as client:
                for check_name in _RUN_ORDER:
                    if check_name not in enabled:
                        continue
                    if check_name == "contract":
                        if openapi_doc is not None:
                            results.append(
                                run_openapi_contract_check(
                                    client=client,
                                    doc=openapi_doc,
                                    config=self._config,
                                )
                            )
                        if graphql_schema is not None:
                            results.append(
                                run_graphql_contract_check(
                                    client=client,
                                    schema=graphql_schema,
                                    config=self._config,
                                )
                            )
                        if openapi_doc is None and graphql_schema is None:
                            results.append(
                                _skip_result(
                                    "contract",
                                    "no OpenAPI / GraphQL document supplied",
                                )
                            )
                    elif check_name == "negative":
                        if openapi_doc is None:
                            results.append(
                                _skip_result(
                                    "negative",
                                    "no OpenAPI document supplied (required for negative variants)",
                                )
                            )
                        else:
                            results.append(
                                run_negative_check(
                                    client=client,
                                    doc=openapi_doc,
                                    config=self._config,
                                )
                            )
                    elif check_name == "auth":
                        results.append(
                            run_auth_check(
                                client=client,
                                doc=openapi_doc,
                                config=self._config,
                                env=dict(os.environ),
                            )
                        )
                    elif check_name == "pagination":
                        if openapi_doc is None:
                            results.append(
                                _skip_result(
                                    "pagination",
                                    "no OpenAPI document supplied "
                                    "(required for paginated endpoint discovery)",
                                )
                            )
                        else:
                            results.append(
                                run_pagination_check(
                                    client=client,
                                    doc=openapi_doc,
                                    config=self._config,
                                )
                            )
                    elif check_name == "error_shape":
                        results.append(
                            run_error_shape_check(
                                results=tuple(results),
                                config=self._config,
                            )
                        )
                    elif check_name == "latency":
                        results.append(
                            run_latency_check(
                                results=tuple(results),
                                config=self._config,
                            )
                        )
                    elif check_name == "backward_compat":
                        previous_root = options.artifacts_root or (Path(".sentinel") / "runs")
                        previous = load_previous_snapshot(
                            artifacts_root=previous_root,
                            current_run_id=ctx.run_id,
                            diff_since_run_id=options.diff_since_run_id,
                        )
                        if previous is None or snapshot is None:
                            results.append(
                                _skip_result(
                                    "backward_compat",
                                    "no prior api-schema.json snapshot available",
                                )
                            )
                        else:
                            results.append(diff_snapshots(previous=previous, current=snapshot))
        except (httpx.HTTPError, OSError) as exc:
            write_audit_entry(
                audit_log_path,
                {
                    "event": "api.error",
                    "run_id": ctx.run_id,
                    "error": exc.__class__.__name__,
                    "message": str(exc)[:512],
                },
            )
            duration_ms = int((perf_counter() - started) * 1000)
            return ApiRunOutcome(
                schema_version=API_RESULT_SCHEMA_VERSION,
                checks=tuple(results),
                duration_ms=duration_ms,
                incomplete=True,
                openapi_loaded=openapi_doc is not None,
                graphql_loaded=graphql_schema is not None,
            )

        duration_ms = int((perf_counter() - started) * 1000)
        write_audit_entry(
            audit_log_path,
            {
                "event": "api.complete",
                "run_id": ctx.run_id,
                "checks_executed": [r.check for r in results],
                "issues": sum(len(r.issues) for r in results),
            },
        )
        return ApiRunOutcome(
            schema_version=API_RESULT_SCHEMA_VERSION,
            checks=tuple(results),
            duration_ms=duration_ms,
            incomplete=False,
            openapi_loaded=openapi_doc is not None,
            graphql_loaded=graphql_schema is not None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_options(ctx: ModuleContext) -> ApiModuleOptions:
    raw: Any = ctx.options.get("api") if "api" in ctx.options else ctx.options
    if isinstance(raw, ApiModuleOptions):
        return raw
    if isinstance(raw, dict):
        return ApiModuleOptions(
            routes=_coerce_str_tuple(raw.get("routes")),
            openapi_path=_coerce_path(raw.get("openapi_path")),
            graphql_path=_coerce_path(raw.get("graphql_path")),
            discovery_path=_coerce_path(raw.get("discovery_path")),
            enabled_checks=_coerce_str_tuple(raw.get("enabled_checks")),
            diff_since_run_id=_coerce_str(raw.get("diff_since_run_id")),
            artifacts_root=_coerce_path(raw.get("artifacts_root")),
            extra_env=raw.get("extra_env", {}),
        )
    return ApiModuleOptions()


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(v) for v in value)
    return ()


def _coerce_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(str(value))


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _resolve_enabled_checks(
    config: RootConfig,
    options: ApiModuleOptions,
) -> tuple[ApiCheckName, ...]:
    configured = tuple(config.api.enabled_checks)
    if options.enabled_checks:
        # Intersect requested with configured so the CLI cannot enable a
        # check the operator's config explicitly turned off.
        requested = set(options.enabled_checks)
        return tuple(c for c in configured if c in requested)
    return configured


def _skip_result(check: ApiCheckName, reason: str) -> ApiCheckResult:
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check=check,
        issues=(),
        targets_scanned=0,
        duration_ms=0,
        skipped=True,
        skip_reason=reason,
    )


def _synthetic_runner_outcome(ctx: ModuleContext, outcome: ApiRunOutcome) -> RunnerOutcome:
    """Build a placeholder :class:`RunnerOutcome` so the base contract holds."""

    status: ModuleStatus
    if not outcome.checks or all(c.skipped for c in outcome.checks):
        status = "skipped"
    elif outcome.incomplete:
        status = "incomplete"
    else:
        status = "passed"
    return RunnerOutcome.build(
        module_name="api",
        module_id=ctx.id_generator.new("MOD"),
        status=status,
        tests=(),
        duration_ms=outcome.duration_ms,
        environment=EnvironmentContext(
            browser=ctx.config.runner.browser,
            browser_version="bundled",
            os="unknown",
        ),
    )


def _factory(config: RootConfig, safety_decision: SafetyDecision) -> ApiModule:
    return ApiModule(config, safety_decision)


def register_with_default_registry(registry: ModuleRegistry | None = None) -> None:
    reg = registry or default_registry()
    if "api" in reg.modules:
        return
    reg.register_module("api", _factory)


_ = datetime.now(UTC)  # ensure import isn't pruned by linters


# Re-export so callers can import ApiIssue from the module package without
# pulling models.py directly.
__all__ = [
    "ApiIssue",
    "ApiModule",
    "ApiModuleOptions",
    "register_with_default_registry",
]
