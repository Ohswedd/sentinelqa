"""``sentinel plan`` — produce a deterministic test plan.

Wires the run-lifecycle steps 1-9: load config → enforce safety → ID +
artifact dir → discover (or re-read prior discovery) → plan → write
``plan.json`` + ``plan.md``. The runner is intentionally not
invoked; this command is the planner-only surface of the lifecycle.

Replaces the stub.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.discovery.auth_boundary import AuthCredentials
from engine.discovery.crawler import CrawlPolicy
from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
from engine.discovery.writer import write_discovery_artifacts
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap
from engine.domain.target import Target
from engine.errors.codes import EXIT_SUCCESS
from engine.planner.core import DeterministicPlanner
from engine.planner.llm_adapter import (
    BudgetExceededError,
    NullLlmPlanner,
    build_llm_planner,
)
from engine.planner.plan_writer import write_plan_artifacts
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_plan(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override `target.base_url` for this planning pass."),
    ] = None,
    from_discovery: Annotated[
        Path | None,
        typer.Option(
            "--from-discovery",
            help=(
                "Reuse an existing run dir (containing discovery.json + risk.json) "
                "instead of running discovery again."
            ),
        ),
    ] = None,
    llm: Annotated[
        bool | None,
        typer.Option(
            "--llm/--no-llm",
            help="Enable/disable the LLM planner adapter (default: config-driven).",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Override the artifact directory parent (default: .sentinel/runs).",
        ),
    ] = None,
    max_depth: Annotated[
        int | None,
        typer.Option("--max-depth", help="Override discovery.max_depth."),
    ] = None,
    max_pages: Annotated[
        int | None,
        typer.Option("--max-pages", help="Override discovery.max_pages."),
    ] = None,
    rate_limit: Annotated[
        float | None,
        typer.Option("--rate-limit", help="Override discovery.rate_limit_rps."),
    ] = None,
) -> None:
    """Produce a test plan from discovery + risk."""

    state: GlobalState = ctx.obj
    config = load_config(state.config_path)
    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )
    if llm is not None:
        config = config.model_copy(
            update={
                "planner": config.planner.model_copy(
                    update={"llm": config.planner.llm.model_copy(update={"enabled": llm})}
                )
            }
        )

    artifacts_root = output if output is not None else Path(".sentinel") / "runs"
    ids = IdGenerator()
    run_id = ids.new("RUN")
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_log_path = run_dir / "audit.log"

    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    SafetyPolicy().enforce(target, audit_log_path=audit_log_path)

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "plan.start",
            "run_id": run_id,
            "target": str(config.target.base_url),
            "from_discovery": str(from_discovery) if from_discovery else None,
            "llm_enabled": config.planner.llm.enabled,
        },
    )

    if from_discovery is not None:
        graph, risk = _load_existing_discovery(from_discovery)
    else:
        graph, risk = _run_discovery(
            config=config,
            run_id=run_id,
            ids=ids,
            run_dir=run_dir,
            max_depth=max_depth,
            max_pages=max_pages,
            rate_limit=rate_limit,
        )

    planner = DeterministicPlanner(id_generator=ids)
    outcome = planner.plan(graph, risk, config, run_id=run_id)
    plan = outcome.plan

    llm_planner = build_llm_planner(config.planner.llm)
    llm_flow_count = 0
    if not isinstance(llm_planner, NullLlmPlanner):
        try:
            llm_flows = llm_planner.propose_flows(graph, plan, id_generator=ids)
        except BudgetExceededError as exc:
            write_audit_entry(
                audit_log_path,
                {
                    "decided_at": datetime.now(UTC).isoformat(),
                    "event": "plan.llm.budget_exceeded",
                    "run_id": run_id,
                    "detail": str(exc),
                },
            )
            llm_flows = ()
        if llm_flows:
            plan = plan.model_copy(
                update={
                    "flows": tuple(plan.flows) + tuple(llm_flows),
                }
            )
            llm_flow_count = len(llm_flows)
        write_audit_entry(
            audit_log_path,
            {
                "decided_at": datetime.now(UTC).isoformat(),
                "event": "plan.llm.usage",
                "run_id": run_id,
                "provider": llm_planner.name,
                "requests": llm_planner.usage.requests,
                "input_tokens": llm_planner.usage.input_tokens,
                "output_tokens": llm_planner.usage.output_tokens,
                "cost_usd": llm_planner.usage.cost_usd,
            },
        )

    written = write_plan_artifacts(plan=plan, out_dir=run_dir)

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "plan.complete",
            "run_id": run_id,
            "flows_total": len(plan.flows),
            "test_cases_total": len(plan.test_cases),
            "llm_flows_added": llm_flow_count,
            "artifacts": {key: str(path) for key, path in written.items()},
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "plan",
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "plan_id": plan.id,
                    "flows": len(plan.flows),
                    "test_cases": len(plan.test_cases),
                    "llm_flows_added": llm_flow_count,
                    "coverage_estimate": dict(plan.coverage_estimate.by_module),
                    "artifacts": {k: str(v) for k, v in written.items()},
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id      : {run_id}\n"
            f"run_dir     : {run_dir}\n"
            f"plan_id     : {plan.id}\n"
            f"flows       : {len(plan.flows)}\n"
            f"test cases  : {len(plan.test_cases)}\n"
            f"llm flows   : {llm_flow_count}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _build_crawl_policy(
    config: RootConfig,
    *,
    max_depth: int | None,
    max_pages: int | None,
    rate_limit: float | None,
) -> CrawlPolicy:
    discovery = config.discovery
    return CrawlPolicy(
        max_depth=max_depth if max_depth is not None else discovery.max_depth,
        max_pages=max_pages if max_pages is not None else discovery.max_pages,
        rate_limit_rps=(rate_limit if rate_limit is not None else discovery.rate_limit_rps),
        request_timeout_seconds=discovery.request_timeout_seconds,
        respect_robots=discovery.respect_robots,
        same_host_only=discovery.same_host_only,
        extra_allowed_hosts=discovery.extra_allowed_hosts,
    )


def _resolve_credentials(config: RootConfig) -> AuthCredentials | None:
    auth = config.auth
    if auth.login_url is None or auth.username_env is None or auth.password_env is None:
        return None
    username = os.environ.get(auth.username_env)
    password = os.environ.get(auth.password_env)
    if not username or not password:
        sys.stderr.write(
            f"sentinel plan: credentials missing "
            f"({auth.username_env}/{auth.password_env} not set); "
            f"skipping authenticated crawl.\n"
        )
        return None
    return AuthCredentials(
        login_url=auth.login_url,
        username_env_name=auth.username_env,
        password_env_name=auth.password_env,
        username=username,
        password=password,
    )


def _run_discovery(
    *,
    config: RootConfig,
    run_id: str,
    ids: IdGenerator,
    run_dir: Path,
    max_depth: int | None,
    max_pages: int | None,
    rate_limit: float | None,
) -> tuple[DiscoveryGraph, RiskMap]:
    policy = _build_crawl_policy(
        config, max_depth=max_depth, max_pages=max_pages, rate_limit=rate_limit
    )
    pipeline = DiscoveryPipeline(id_generator=ids)
    inputs = DiscoveryInputs(
        base_url=str(config.target.base_url),
        run_id=run_id,
        policy=policy,
        credentials=_resolve_credentials(config),
        openapi_path=config.discovery.openapi.path,
        openapi_url=config.discovery.openapi.url,
        graphql_sdl_path=config.discovery.graphql.path,
        graphql_endpoint_url=config.discovery.graphql.url,
    )
    result = pipeline.run(inputs)
    write_discovery_artifacts(result=result, out_dir=run_dir)
    return result.graph, result.risk_map


def _load_existing_discovery(run_dir: Path) -> tuple[DiscoveryGraph, RiskMap]:
    """Re-parse discovery.json + risk.json from an existing run directory."""

    discovery_path = run_dir / "discovery.json"
    risk_path = run_dir / "risk.json"
    if not discovery_path.exists():
        raise typer.BadParameter(f"{discovery_path} not found.")
    if not risk_path.exists():
        raise typer.BadParameter(f"{risk_path} not found.")
    discovery_payload = json.loads(discovery_path.read_text(encoding="utf-8"))
    risk_payload = json.loads(risk_path.read_text(encoding="utf-8"))
    graph = DiscoveryGraph.model_validate(discovery_payload["graph"])
    risk = RiskMap.model_validate(risk_payload["risk_map"])
    return graph, risk


__all__ = ["run_plan"]
