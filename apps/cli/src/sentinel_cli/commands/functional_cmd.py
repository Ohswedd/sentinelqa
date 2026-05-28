"""``sentinel functional`` — exercise PRD §10.1 functional flows (task 10.04).

Replaces the Phase 02 stub. The command drives the full :class:`RunLifecycle`
restricted to the ``functional`` module so the same lifecycle steps
(safety policy, artifact tree, reporter dispatch, exit-code mapping) run
whether the user types ``sentinel audit`` or ``sentinel functional``.

The command thinly wraps the FunctionalModule (Phase 10.01):

- Slice mode (`--mode smoke|standard|full`) and `--grep` are merged
  into a single Playwright grep via :class:`modules.functional.tags.TagSelection`.
- `--workers`, `--shard`, `--retries` map directly onto the runner config.
- `--url` overrides ``target.base_url`` for this invocation only.

Exit codes follow the canonical grid (CLAUDE §13):

- ``0`` — every functional test passed (no findings ≥ high).
- ``1`` — quality gate failed (flake rate exceeded or blocking findings).
- ``2`` — invalid config or CLI usage (also: shard parse error).
- ``4`` — safety policy blocked the target.
- ``5`` — sentinel-ts binary missing.
- ``6`` — runner failed to execute (e.g. ModulePrerequisiteError, spawn).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from engine.config.loader import load_config
from engine.errors.base import ConfigError
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.policy.audit_log import write_audit_entry
from engine.runner.sharding import ShardSpec

# Ensure the functional module is registered with the process-wide registry.
import modules.functional  # noqa: F401  (side-effect import for registration)
from modules.functional.tags import TagSelection, supported_modes
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_functional(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Slice mode: smoke | standard | full (default: standard).",
        ),
    ] = "standard",
    grep: Annotated[
        str | None,
        typer.Option(
            "--grep",
            help=(
                "Playwright --grep pattern (matches tags + titles). "
                "Combined with --mode via intersection."
            ),
        ),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", min=1, max=64, help="Override runner.workers."),
    ] = None,
    shard: Annotated[
        str | None,
        typer.Option("--shard", help="Run only shard N/M (e.g. 1/4)."),
    ] = None,
    retries: Annotated[
        int | None,
        typer.Option("--retries", min=0, max=10, help="Override runner.retries.max."),
    ] = None,
    spec_root: Annotated[
        Path | None,
        typer.Option(
            "--spec-root",
            help="Spec root directory (default: tests/sentinel/).",
        ),
    ] = None,
) -> None:
    """Run the functional module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    if mode not in supported_modes():
        sys.stderr.write(
            f"sentinel functional: --mode={mode!r} unknown; "
            f"expected one of {supported_modes()}.\n"
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel functional: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )
    if retries is not None:
        config = config.model_copy(
            update={
                "runner": config.runner.model_copy(
                    update={
                        "retries": config.runner.retries.model_copy(update={"max": retries}),
                    }
                )
            }
        )

    shard_spec: ShardSpec | None = None
    if shard is not None:
        try:
            shard_spec = ShardSpec.parse(shard)
        except ValueError as exc:
            sys.stderr.write(f"sentinel functional: {exc}\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    selection = TagSelection.resolve(mode=mode, user_grep=grep)
    module_options: dict[str, Any] = {
        "spec_root": spec_root,
        "grep": selection.grep,
        "shard": shard_spec,
        "workers": workers,
    }

    artifacts_root = Path(".sentinel") / "runs"

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["functional"],
        ci=state.ci,
        module_options={"functional": module_options},
    )

    # Aggregate module + finding counts.
    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "functional"),
        None,
    )
    finding_count = len(typed_module.findings) if typed_module is not None else 0
    high_or_critical = (
        sum(1 for f in typed_module.findings if f.severity in {"critical", "high"})
        if typed_module is not None
        else 0
    )

    if test_run.status == "unsafe_blocked":
        exit_code = EXIT_UNSAFE_TARGET
    elif test_run.status in {"passed", "dry_run"} and high_or_critical == 0:
        exit_code = EXIT_SUCCESS
    elif typed_module is not None and typed_module.status == "failed":
        exit_code = EXIT_QUALITY_GATE_FAILED
    elif test_run.status == "incomplete":
        # Module raised inside the orchestrator → already recorded as an
        # outcome; surface as quality-gate failure so CI doesn't silently
        # pass an incomplete run.
        exit_code = EXIT_QUALITY_GATE_FAILED
    else:
        exit_code = EXIT_SUCCESS

    audit_log_path = artifacts_root / test_run.id / "audit.log"
    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "functional.complete",
            "run_id": test_run.id,
            "module_status": typed_module.status if typed_module else "skipped",
            "findings": finding_count,
            "high_or_critical": high_or_critical,
            "mode": selection.mode,
            "grep": selection.grep,
            "exit_code": exit_code,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "functional",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "module_status": typed_module.status if typed_module else "skipped",
                    "mode": selection.mode,
                    "grep": selection.grep,
                    "findings": finding_count,
                    "high_or_critical": high_or_critical,
                    "exit_code": exit_code,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id            : {test_run.id}\n"
            f"run_status        : {test_run.status}\n"
            f"module_status     : {typed_module.status if typed_module else 'skipped'}\n"
            f"mode              : {selection.mode}\n"
            f"grep              : {selection.grep or '<none>'}\n"
            f"findings          : {finding_count}\n"
            f"high_or_critical  : {high_or_critical}\n"
        )

    raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


__all__ = ["run_functional"]
