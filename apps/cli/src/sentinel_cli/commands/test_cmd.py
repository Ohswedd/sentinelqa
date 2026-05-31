"""``sentinel test`` — run the Playwright runner (task 08.06).

Replaces the Phase 02 stub. The command exercises the
config/safety/runner slice of the lifecycle: discovery / planning /
generation are intentionally skipped unless ``--with-generate`` is
passed (most users run ``sentinel generate`` first and ``sentinel test``
on every push).

Exit codes follow the canonical grid:

- ``0`` — every test passed (or quarantined entries kept the gate green).
- ``1`` — quality gate failed (flake rate exceeded or blocking failures).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
- ``5`` — sentinel-ts binary missing.
- ``6`` — runner failed to execute (spawn error, partial stream).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from engine.auth import (
    SessionHandle,
    Vault,
    cleanup_storage_state,
    materialize_storage_state,
)
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.errors.base import AuthError, ConfigError, UnsafeTargetError
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy
from engine.runner import (
    DockerRunner,
    DockerRunnerError,
    LocalRunner,
    LocalRunnerError,
    Quarantine,
    QuarantineError,
    RunnerSpawnError,
    ShardSpec,
)
from engine.runner.local import RunnerInvocation

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

DEFAULT_TEST_GLOB = "tests/sentinel/**/*.spec.ts"


def run_test(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            help="Spec root or single .spec.ts file (default: tests/sentinel/).",
        ),
    ] = Path("tests/sentinel"),
    grep: Annotated[
        str | None,
        typer.Option("--grep", help="Substring filter applied to spec file paths."),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", min=1, max=64, help="Override runner.workers."),
    ] = None,
    shard: Annotated[
        str | None,
        typer.Option("--shard", help="Run only shard N/M (e.g. 1/4)."),
    ] = None,
    browser: Annotated[
        str | None,
        typer.Option("--browser", help="chromium | firefox | webkit."),
    ] = None,
    docker: Annotated[
        bool,
        typer.Option(
            "--docker/--no-docker",
            help="Run inside the pinned Playwright container (Phase 08.02).",
        ),
    ] = False,
    retries: Annotated[
        int | None,
        typer.Option("--retries", min=0, max=10, help="Override runner.retries.max."),
    ] = None,
    module_name: Annotated[
        str,
        typer.Option(
            "--module",
            help="Module name attached to the run (default: 'functional').",
        ),
    ] = "functional",
    with_generate: Annotated[
        bool,
        typer.Option(
            "--with-generate/--no-generate",
            help="Run `sentinel generate` first so specs exist before testing.",
        ),
    ] = False,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
) -> None:
    """Run generated Playwright tests and emit a RunnerOutcome."""

    state: GlobalState = ctx.obj
    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel test: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )
    if browser is not None:
        config = config.model_copy(
            update={"runner": config.runner.model_copy(update={"browser": browser})}
        )
    if retries is not None:
        config = config.model_copy(
            update={
                "runner": config.runner.model_copy(
                    update={"retries": config.runner.retries.model_copy(update={"max": retries})}
                )
            }
        )

    artifacts_root = Path(".sentinel") / "runs"
    artifacts_root.mkdir(parents=True, exist_ok=True)
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
    safety_policy = SafetyPolicy()
    try:
        safety_policy.enforce(target, audit_log_path=audit_log_path)
    except UnsafeTargetError as exc:
        write_audit_entry(
            audit_log_path,
            {
                "decided_at": datetime.now(UTC).isoformat(),
                "event": "test.unsafe_blocked",
                "host": exc.technical_context.get("host"),
            },
        )
        sys.stderr.write(f"sentinel test: {exc.message}\n")
        raise typer.Exit(code=EXIT_UNSAFE_TARGET) from exc

    # Quarantine — load before spawn so an expired entry fails fast.
    try:
        quarantine = Quarantine.load(
            config.runner.quarantine.path,
            max_age_days=config.runner.quarantine.max_age_days,
        )
    except QuarantineError as exc:
        sys.stderr.write(f"sentinel test: quarantine load failed: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if with_generate:
        try:
            _generate_before_test(ctx, config, run_id, ids, run_dir)
        except typer.Exit:
            raise
        except Exception as exc:
            sys.stderr.write(f"sentinel test --with-generate: {exc}\n")
            raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED) from exc

    specs = _discover_specs(path, grep)
    if not specs:
        sys.stderr.write(
            f"sentinel test: no specs matched `{path}` "
            f"({'with grep=' + grep if grep else 'no filter'}). "
            "Run `sentinel generate` first.\n"
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    shard_spec: ShardSpec | None = None
    if shard is not None:
        try:
            shard_spec = ShardSpec.parse(shard)
        except ValueError as exc:
            sys.stderr.write(f"sentinel test: {exc}\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    # Phase 31, ADR-0043. If the operator selected
    # ``auth.strategy: browser_session``, decrypt the vault entry into a
    # short-lived plaintext file under ``<run-dir>/auth/``. The file is
    # cleaned up before the command returns; the orchestrator never
    # copies it into report artifacts.
    session_handle: SessionHandle | None = None
    if config.auth.strategy == "browser_session":
        try:
            session_handle = materialize_storage_state(
                Vault(),
                host=_target_host(str(config.target.base_url)),
                name=config.auth.session_name or "",
                run_dir=run_dir,
                allowed_hosts=config.target.allowed_hosts,
                audit_log_path=audit_log_path,
            )
        except AuthError as exc:
            sys.stderr.write(f"sentinel test: {exc.message}\n")
            raise typer.Exit(code=exc.exit_code) from exc

    invocation = RunnerInvocation(
        run_id=run_id,
        run_dir=run_dir,
        target=str(config.target.base_url),
        module_name=module_name,
        spec_files=specs,
        shard=shard_spec,
        workers=workers,
        quarantine=quarantine,
        storage_state_path=session_handle.path if session_handle else None,
    )

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "test.start",
            "run_id": run_id,
            "module": module_name,
            "specs": len(specs),
            "docker": docker,
            "shard": str(shard_spec) if shard_spec else None,
        },
    )

    try:
        if docker:
            outcome = DockerRunner(
                config=config,
                target=target,
                safety_policy=safety_policy,
                id_generator=ids,
            ).run(invocation)
        else:
            outcome = LocalRunner(config=config, id_generator=ids).run(invocation)
    except RunnerSpawnError as exc:
        sys.stderr.write(f"sentinel test: {exc}\n")
        raise typer.Exit(code=EXIT_DEPENDENCY_MISSING) from exc
    except DockerRunnerError as exc:
        sys.stderr.write(f"sentinel test: docker runner failed: {exc}\n")
        raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED) from exc
    except LocalRunnerError as exc:
        sys.stderr.write(f"sentinel test: runner failed: {exc}\n")
        raise typer.Exit(code=EXIT_TEST_EXECUTION_FAILED) from exc
    finally:
        # Phase 31, ADR-0043. The plaintext storage_state file MUST NOT
        # outlive the run; we drop it as soon as the runner returns,
        # regardless of outcome (success, gate-fail, spawn-error, crash).
        if session_handle is not None:
            cleanup_storage_state(session_handle)

    gate_failed = _gate_failed(outcome, config)
    exit_code = (
        EXIT_QUALITY_GATE_FAILED
        if gate_failed
        else EXIT_TEST_EXECUTION_FAILED
        if outcome.module_result.status in {"failed", "errored", "incomplete"}
        else EXIT_SUCCESS
    )

    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "test.complete",
            "run_id": run_id,
            "module": module_name,
            "status": outcome.module_result.status,
            "tests_total": int(outcome.module_result.metrics.get("tests_total", 0)),
            "tests_failed": int(outcome.module_result.metrics.get("tests_failed", 0)),
            "flake_rate": outcome.flake_rate,
            "exit_code": exit_code,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "test",
                    "run_id": run_id,
                    "module": module_name,
                    "status": outcome.module_result.status,
                    "metrics": outcome.module_result.metrics,
                    "flake_rate": outcome.flake_rate,
                    "tests": [t.model_dump(mode="json") for t in outcome.tests],
                    "exit_code": exit_code,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id     : {run_id}\n"
            f"module     : {module_name}\n"
            f"status     : {outcome.module_result.status}\n"
            f"tests      : {int(outcome.module_result.metrics.get('tests_total', 0))}\n"
            f"passed     : {int(outcome.module_result.metrics.get('tests_passed', 0))}\n"
            f"failed     : {int(outcome.module_result.metrics.get('tests_failed', 0))}\n"
            f"flaky      : {int(outcome.module_result.metrics.get('tests_flaky', 0))}\n"
            f"flake_rate : {outcome.flake_rate:.3f} "
            f"(max {config.policy.max_flake_rate:.3f})\n"
        )

    raise typer.Exit(code=exit_code)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _target_host(base_url: str) -> str:
    """Return the lower-cased host from a ``target.base_url`` value.

    Phase 31, ADR-0043 — used by `auth.strategy: browser_session` to
    look the session up by host. Returns an empty string when the URL
    is malformed; the vault then raises ``VaultEntryNotFoundError`` and
    the caller surfaces a precise error to the operator.
    """

    return (urlparse(base_url).hostname or "").lower()


def _generate_before_test(
    ctx: typer.Context,
    config: RootConfig,
    run_id: str,
    ids: IdGenerator,
    run_dir: Path,
) -> None:
    """Re-generate specs against ``config.target.base_url`` before running tests.

    Mirrors the discovery+planner+generator chain from ``run_generate`` but
    inlines it so we don't have to redirect typer.Context. The generated
    specs are written to ``tests/sentinel/`` (the default test root) so
    ``run_test`` picks them up.
    """

    from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
    from engine.generator import (
        GenerationInputs,
        GenerationOptions,
        GeneratorPipeline,
        write_generated_files,
    )
    from engine.planner.core import DeterministicPlanner

    from sentinel_cli.commands.generate_cmd import (
        _build_crawl_policy,
        _resolve_credentials,
    )

    discovery_pipeline = DiscoveryPipeline(id_generator=ids)
    disc_inputs = DiscoveryInputs(
        base_url=str(config.target.base_url),
        run_id=run_id,
        policy=_build_crawl_policy(config),
        credentials=_resolve_credentials(config),
        openapi_path=config.discovery.openapi.path,
        openapi_url=config.discovery.openapi.url,
        graphql_sdl_path=config.discovery.graphql.path,
        graphql_endpoint_url=config.discovery.graphql.url,
    )
    discovery_result = discovery_pipeline.run(disc_inputs)
    plan_outcome = DeterministicPlanner(id_generator=ids).plan(
        discovery_result.graph, discovery_result.risk_map, config, run_id=run_id
    )
    out_root = Path("tests").resolve()
    options = GenerationOptions(
        base_url=str(config.target.base_url),
        login_url=str(config.auth.login_url) if config.auth.login_url is not None else None,
        username_env=config.auth.username_env,
        password_env=config.auth.password_env,
        security_mode=config.security.mode,
    )
    generated = GeneratorPipeline().generate(
        GenerationInputs(
            plan=plan_outcome.plan,
            graph=discovery_result.graph,
            out_dir=out_root,
            options=options,
        )
    )
    write_generated_files(
        [(f.path, f.content) for f in generated.files],
        force=False,
    )


def _discover_specs(path: Path, grep: str | None) -> list[Path]:
    """Resolve the spec path (file or directory) into a list of spec files."""

    if path.is_file() and path.suffix == ".ts":
        return [path] if (grep is None or grep in str(path)) else []
    if not path.exists():
        return []
    out: list[Path] = []
    for spec in sorted(path.rglob("*.spec.ts")):
        if grep is not None and grep not in str(spec):
            continue
        out.append(spec)
    return out


def _gate_failed(outcome: object, config: RootConfig) -> bool:
    # Phase 14 owns the full score-gate computation. For Phase 08 we
    # surface only the flake-rate gate so quarantine is honored.
    flake_rate = float(getattr(outcome, "flake_rate", 0.0))
    return flake_rate > config.policy.max_flake_rate


# Suppress unused-import warnings — asyncio / os are kept on the namespace
# for tests that import them via this module path.
__all__ = ["run_test"]
_UNUSED: tuple[object, ...] = (asyncio, os)
