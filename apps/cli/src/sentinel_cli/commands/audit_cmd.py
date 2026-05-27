"""`sentinel audit` — invoke the canonical run lifecycle (task 02.04).

In Phase 02 no module phases have shipped yet, so audit runs the
lifecycle with an empty module registry. The output is the artifact
tree + `run.json` + audit log. Module phases (05+) register themselves
into the orchestrator and audit's behavior expands automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.config.loader import load_config
from engine.errors.codes import (
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_audit(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option(
            "--url",
            help="Override `target.base_url` for this run.",
        ),
    ] = None,
    modules: Annotated[
        str | None,
        typer.Option(
            "--modules",
            help="Comma-separated module names to run (default: all enabled in config).",
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
    fail_under: Annotated[
        int | None,
        typer.Option(
            "--fail-under",
            help="Override policy.min_quality_score for the run.",
        ),
    ] = None,
) -> None:
    """Execute the full audit lifecycle."""

    state: GlobalState = ctx.obj

    config = load_config(state.config_path)

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )
    if fail_under is not None:
        config = config.model_copy(
            update={"policy": config.policy.model_copy(update={"min_quality_score": fail_under})}
        )

    requested_modules: list[str] | None = None
    if modules:
        requested_modules = [m.strip() for m in modules.split(",") if m.strip()]

    artifacts_root = output if output is not None else Path(".sentinel") / "runs"

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=requested_modules,
        dry_run=state.dry_run,
        ci=state.ci,
    )

    exit_code = _status_to_exit_code(test_run.status)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "audit",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "modules_run": list(test_run.modules_run),
                    "started_at": test_run.started_at.isoformat(),
                    "finished_at": (
                        test_run.finished_at.isoformat() if test_run.finished_at else None
                    ),
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id   : {test_run.id}\n"
            f"status   : {test_run.status}\n"
            f"modules  : {', '.join(test_run.modules_run) or '(none)'}\n"
        )

    if exit_code != EXIT_SUCCESS:
        raise typer.Exit(code=exit_code)


def _status_to_exit_code(status: str) -> int:
    """Map :class:`engine.domain.test_run.RunStatus` to a CLI exit code."""

    if status == "passed":
        return EXIT_SUCCESS
    if status == "dry_run":
        return EXIT_SUCCESS
    if status == "failed":
        return EXIT_QUALITY_GATE_FAILED
    if status == "unsafe_blocked":
        return EXIT_UNSAFE_TARGET
    if status == "incomplete":
        # Some modules errored; we did not get a complete answer. Surface
        # as test-execution failure so CI fails by default.
        return EXIT_TEST_EXECUTION_FAILED
    return EXIT_SUCCESS


__all__ = ["run_audit"]
