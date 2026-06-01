"""`sentinel audit` — invoke the canonical run lifecycle.

In no module phases have shipped yet, so audit runs the
lifecycle with an empty module registry. The output is the artifact
tree + `run.json` + audit log. Module phases (05+) register themselves
into the orchestrator and audit's behavior expands automatically.

adds ``--compliance-pack`` so operators can drive a run with
a named (or path-resolved) compliance pack (WCAG 2.2 AA, GDPR
baseline, CCPA baseline, SOC 2 trail). The pack composes the modules,
per-module options, and check filter for the run.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from engine.config.loader import load_config
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.policy.compliance import (
    CompliancePack,
    CompliancePackError,
    load_compliance_pack,
)

# Side-effect import — registers the compliance module so the
# ``--compliance-pack`` flag can reference it.
import modules.compliance  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState
from sentinel_cli.watch import WatchOptions, emit_to_stderr, watch_loop


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
    compliance_pack: Annotated[
        str | None,
        typer.Option(
            "--compliance-pack",
            help=(
                "Built-in pack id (e.g. wcag-2.2-aa, gdpr-baseline, "
                "ccpa-baseline, soc2-trail) or a path to a custom "
                "compliance pack YAML."
            ),
        ),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help=(
                "Re-run the audit on file changes (local dev loop). " "Refuses to start in CI mode."
            ),
        ),
    ] = False,
    watch_root: Annotated[
        Path | None,
        typer.Option(
            "--watch-root",
            help=(
                "Directory to watch (default: current directory). " "Only meaningful with --watch."
            ),
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

    pack: CompliancePack | None = None
    module_options: dict[str, dict[str, object]] | None = None
    if compliance_pack is not None:
        try:
            pack = load_compliance_pack(compliance_pack)
        except CompliancePackError as exc:
            sys.stderr.write(f"compliance pack error: {exc}\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc
        # ``--modules`` is the explicit user override; when present it
        # constrains the run to that set (even when the pack lists more).
        # Without ``--modules``, the pack drives the requested-module
        # list directly.
        if requested_modules is None:
            requested_modules = list(pack.requested_modules())
        module_options = pack.module_options()

    artifacts_root = output if output is not None else Path(".sentinel") / "runs"

    if watch:
        if state.ci:
            sys.stderr.write(
                "--watch is intended for local development; refusing to start in CI mode.\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

        def _run_once() -> None:
            lifecycle = RunLifecycle(artifacts_root=artifacts_root)
            run = lifecycle.execute(
                config,
                requested_modules=requested_modules,
                dry_run=state.dry_run,
                ci=state.ci,
                module_options=module_options,
            )
            if state.mode != "quiet":
                sys.stdout.write(f"[watch] run {run.id} → {run.status}\n")
                sys.stdout.flush()

        root = (watch_root or Path(".")).resolve()
        try:
            watch_loop(
                WatchOptions(root=root),
                _run_once,
                out=emit_to_stderr,
            )
        except KeyboardInterrupt:
            sys.stderr.write("\n[watch] interrupted; exiting.\n")
        return

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=requested_modules,
        dry_run=state.dry_run,
        ci=state.ci,
        module_options=module_options,
    )

    exit_code = _status_to_exit_code(test_run.status)

    if state.mode == "json":
        with json_stdout() as out:
            payload: dict[str, object] = {
                "command": "audit",
                "run_id": test_run.id,
                "status": test_run.status,
                "modules_run": list(test_run.modules_run),
                "started_at": test_run.started_at.isoformat(),
                "finished_at": (test_run.finished_at.isoformat() if test_run.finished_at else None),
            }
            if pack is not None:
                payload["compliance_pack"] = pack.id
            out.emit(payload)
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id   : {test_run.id}\n"
            f"status   : {test_run.status}\n"
            f"modules  : {', '.join(test_run.modules_run) or '(none)'}\n"
        )
        if pack is not None:
            sys.stdout.write(f"pack     : {pack.id} ({pack.label})\n")

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
