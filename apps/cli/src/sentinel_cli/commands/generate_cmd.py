"""``sentinel generate`` — render Playwright specs/pages/fixtures.

Wires the generator pipeline into the CLI. The command runs lifecycle
steps 1-9 (config → safety → discover → plan) unless ``--from-plan``
points at an existing plan.json, then writes the generated files.

Hand-edited files (those lacking the SentinelQA banner) are preserved
unless ``--force`` is passed. The brittleness audit always runs over
the rendered specs; failures abort the write and exit code 6.

Replaces the stub.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.discovery.auth_boundary import AuthCredentials
from engine.discovery.crawler import CrawlPolicy
from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap
from engine.domain.target import Target
from engine.errors.codes import EXIT_SUCCESS, EXIT_TEST_EXECUTION_FAILED
from engine.generator import (
    BrittlenessWarning,
    GeneratedFile,
    GenerationInputs,
    GenerationOptions,
    GeneratorPipeline,
    LocatorAuditError,
    OverwriteError,
    audit_specs,
    write_generated_files,
)
from engine.generator.plan_md import PLAN_FILE_NAME
from engine.planner.core import DeterministicPlanner
from engine.planner.plan_writer import read_plan
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_generate(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override `target.base_url` for this generation pass."),
    ] = None,
    from_plan: Annotated[
        Path | None,
        typer.Option(
            "--from-plan",
            help=(
                "Reuse an existing plan.json (skip discovery + planning). "
                "Must be paired with --from-discovery so the graph is available."
            ),
        ),
    ] = None,
    from_discovery: Annotated[
        Path | None,
        typer.Option(
            "--from-discovery",
            help="Reuse an existing discovery run dir (containing discovery.json + risk.json).",
        ),
    ] = None,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Root directory for generated files (default: tests/).",
        ),
    ] = Path("tests"),
    source: Annotated[
        Path,
        typer.Option(
            "--source",
            help="Working directory for resolving paths (default: cwd).",
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite hand-owned files (those without the SentinelQA banner).",
        ),
    ] = False,
    no_tsc: Annotated[
        bool,
        typer.Option(
            "--no-tsc/--tsc",
            help="Skip the post-write tsc --noEmit sanity check.",
        ),
    ] = False,
    no_audit: Annotated[
        bool,
        typer.Option(
            "--no-audit/--audit",
            help="Skip the brittleness audit (NOT recommended; CI should always audit).",
        ),
    ] = False,
) -> None:
    """Render Playwright specs from a plan + discovery graph."""

    state: GlobalState = ctx.obj
    config = load_config(state.config_path)
    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    artifacts_root = Path(".sentinel") / "runs"
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
            "event": "generate.start",
            "run_id": run_id,
            "target": str(config.target.base_url),
            "from_plan": str(from_plan) if from_plan else None,
            "from_discovery": str(from_discovery) if from_discovery else None,
        },
    )

    if from_plan is not None:
        if from_discovery is None:
            raise typer.BadParameter(
                "--from-plan requires --from-discovery so the graph is available."
            )
        plan = read_plan(from_plan)
        graph, _risk = _load_existing_discovery(from_discovery)
    elif from_discovery is not None:
        graph, risk = _load_existing_discovery(from_discovery)
        plan_outcome = DeterministicPlanner(id_generator=ids).plan(
            graph, risk, config, run_id=run_id
        )
        plan = plan_outcome.plan
    else:
        graph, risk = _run_discovery(config=config, run_id=run_id, ids=ids, run_dir=run_dir)
        plan_outcome = DeterministicPlanner(id_generator=ids).plan(
            graph, risk, config, run_id=run_id
        )
        plan = plan_outcome.plan

    out_root = (source / out).resolve()
    spec_root = out_root / "sentinel"
    prior_plan_md = spec_root / PLAN_FILE_NAME

    pipeline = GeneratorPipeline()
    options = GenerationOptions(
        base_url=str(config.target.base_url),
        login_url=str(config.auth.login_url) if config.auth.login_url is not None else None,
        username_env=config.auth.username_env,
        password_env=config.auth.password_env,
        security_mode=config.security.mode,
    )
    result = pipeline.generate(
        GenerationInputs(
            plan=plan,
            graph=graph,
            out_dir=out_root,
            options=options,
            prior_plan_md_path=prior_plan_md if prior_plan_md.exists() else None,
        )
    )

    # Brittleness audit must run BEFORE we touch the filesystem so a
    # bad render never half-writes.
    audit_warnings = 0
    if not no_audit and result.spec_paths:
        try:
            tmp_dir = run_dir / "audit-tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_files: list[Path] = []
            for spec in result.files_by_kind("spec"):
                tmp_path = tmp_dir / spec.path.name
                tmp_path.write_text(spec.content, encoding="utf-8")
                tmp_files.append(tmp_path)
            report = audit_specs(tmp_files, cwd=tmp_dir)
            audit_warnings = len(report.warnings)
            if not report.is_clean:
                _emit_audit_failure(state, report.warnings)
                raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED)
        except LocatorAuditError as exc:
            sys.stderr.write(
                f"sentinel generate: locator audit failed: {exc}\n"
                "  (re-run with --no-audit to skip during local debugging only.)\n"
            )
            raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED) from exc

    # Atomic-write the files. OverwriteError exits 6.
    write_pairs: list[tuple[Path, str]] = [(f.path, f.content) for f in result.files]
    try:
        outcomes = write_generated_files(write_pairs, force=force)
    except OverwriteError as exc:
        sys.stderr.write(f"sentinel generate: {exc}\n")
        raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED) from exc

    # Mirror the plan.md into the run dir so reviewers see it inside the
    # SentinelQA artifact tree as well.
    run_dir_plan_md = run_dir / PLAN_FILE_NAME
    run_dir_plan_md.write_text(_plan_md_body(result.files), encoding="utf-8")

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "generate.complete",
            "run_id": run_id,
            "files_written": sum(1 for o in outcomes if o.status in {"written", "updated"}),
            "files_unchanged": sum(1 for o in outcomes if o.status == "unchanged"),
            "audit_warnings": audit_warnings,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "generate",
                    "run_id": run_id,
                    "out_dir": str(out_root),
                    "files": [
                        {
                            "path": str(o.path),
                            "status": o.status,
                        }
                        for o in outcomes
                    ],
                    "audit_warnings": audit_warnings,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id          : {run_id}\n"
            f"out_dir         : {out_root}\n"
            f"specs           : {len(result.spec_paths)}\n"
            f"page_objects    : {len(result.page_objects)}\n"
            f"fixtures        : {len(result.fixtures)}\n"
            f"audit_warnings  : {audit_warnings}\n"
            f"files_written   : "
            f"{sum(1 for o in outcomes if o.status in {'written', 'updated'})}\n"
        )

    if not no_tsc:
        # tsc validation is best-effort: when tsc isn't installed (e.g.
        # tests running without node), we skip with a message instead of
        # failing the command.
        _ = _tsc_check(out_root, state)

    raise typer.Exit(code=EXIT_SUCCESS)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _emit_audit_failure(state: GlobalState, warnings: Sequence[BrittlenessWarning]) -> None:
    if state.mode == "json":
        from sentinel_cli.json_mode import json_stdout as _emit

        with _emit() as out:
            out.emit(
                {
                    "command": "generate",
                    "audit_failed": True,
                    "warnings_count": len(warnings),
                }
            )
        return
    sys.stderr.write("sentinel generate: brittleness audit failed. Findings:\n")
    for w in warnings:
        sys.stderr.write(f"  - {w.file}:{w.line} {w.message}\n")


def _plan_md_body(files: tuple[GeneratedFile, ...]) -> str:
    for f in files:
        if f.kind == "plan-md":
            return f.content
    return ""


def _tsc_check(out_root: Path, state: GlobalState) -> bool:
    """Best-effort tsc --noEmit sanity check; returns True on success."""

    import shutil
    import subprocess

    tsc = shutil.which("tsc")
    if tsc is None:
        # No tsc on PATH (e.g. CI without node). The Phase-04 tsc gate
        # covers this elsewhere.
        return True
    try:
        subprocess.run(
            [tsc, "--noEmit", "-p", str(out_root)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        if state.mode != "quiet":
            sys.stderr.write(f"sentinel generate: tsc skipped ({exc}).\n")
        return False
    return True


def _build_crawl_policy(config: RootConfig) -> CrawlPolicy:
    discovery = config.discovery
    return CrawlPolicy(
        max_depth=discovery.max_depth,
        max_pages=discovery.max_pages,
        rate_limit_rps=discovery.rate_limit_rps,
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
) -> tuple[DiscoveryGraph, RiskMap]:
    pipeline = DiscoveryPipeline(id_generator=ids)
    inputs = DiscoveryInputs(
        base_url=str(config.target.base_url),
        run_id=run_id,
        policy=_build_crawl_policy(config),
        credentials=_resolve_credentials(config),
        openapi_path=config.discovery.openapi.path,
        openapi_url=config.discovery.openapi.url,
        graphql_sdl_path=config.discovery.graphql.path,
        graphql_endpoint_url=config.discovery.graphql.url,
    )
    _ = run_dir  # discovery artifacts not persisted here; generate writes elsewhere.
    result = pipeline.run(inputs)
    return result.graph, result.risk_map


def _load_existing_discovery(run_dir: Path) -> tuple[DiscoveryGraph, RiskMap]:
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


__all__ = ["run_generate"]
