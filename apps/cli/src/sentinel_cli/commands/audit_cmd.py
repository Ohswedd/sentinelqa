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
from engine.cache import compute_fingerprint
from engine.cache.run_info import read_cache_report
from engine.config.loader import load_config
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.changed_modules import (
    GitNotAvailableError,
    select_modules,
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
    changed_only: Annotated[
        bool,
        typer.Option(
            "--changed-only",
            help=(
                "Restrict the run to modules impacted by the git diff "
                "against --diff-base. Exits 0 with no modules run when "
                "no audit-relevant files changed (docs, README, etc.)."
            ),
        ),
    ] = False,
    diff_base: Annotated[
        str,
        typer.Option(
            "--diff-base",
            help=("Git ref to diff against when --changed-only is set " "(default: origin/main)."),
        ),
    ] = "origin/main",
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help=(
                "Skip the run when the source fingerprint matches the "
                "given run id's (use 'latest' to point at the most recent "
                "run). Useful in CI: 'sentinel audit --since latest' is "
                "a no-op when nothing source-relevant changed."
            ),
        ),
    ] = None,
    parallel_modules: Annotated[
        int,
        typer.Option(
            "--parallel-modules",
            min=1,
            max=16,
            help=(
                "Number of modules to execute concurrently after the "
                "safety policy enforces (default: 1 = sequential). "
                "Modules run on a bounded thread pool; outcomes are "
                "collected in input order."
            ),
        ),
    ] = 1,
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

    # --since: short-circuit the whole audit if the prior run's source
    # fingerprint matches the current one. Read-only: we never mutate
    # the prior run; we only compare its cache.json.
    if since is not None:
        target_dir = artifacts_root / "latest" if since == "latest" else artifacts_root / since
        prior_cache = read_cache_report(target_dir / "cache.json")
        if prior_cache is None or prior_cache.source_fingerprint is None:
            sys.stderr.write(
                f"--since: no readable cache.json under {target_dir!s}; running normally.\n"
            )
        else:
            current_fp = compute_fingerprint(Path.cwd())
            if current_fp.hash == prior_cache.source_fingerprint.hash:
                if state.mode == "json":
                    with json_stdout() as out:
                        out.emit(
                            {
                                "command": "audit",
                                "status": "unchanged",
                                "since_run_id": prior_cache.source_fingerprint.short,
                                "fingerprint": current_fp.hash,
                            }
                        )
                elif state.mode != "quiet":
                    sys.stdout.write(
                        f"source unchanged since {target_dir.name} "
                        f"(fingerprint {current_fp.short()}); no audit needed.\n"
                    )
                return

    # --changed-only: restrict requested_modules to the diff-impacted set.
    if changed_only:
        try:
            selection = select_modules(
                diff_base,
                cwd=Path.cwd(),
                intersect_with=(frozenset(requested_modules) if requested_modules else None),
            )
        except GitNotAvailableError as exc:
            sys.stderr.write(f"--changed-only: {exc}\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc
        if selection.empty():
            if state.mode == "json":
                with json_stdout() as out:
                    out.emit(
                        {
                            "command": "audit",
                            "status": "no-op",
                            "diff_base": diff_base,
                            "changed_files": [str(p) for p in selection.changed_files],
                        }
                    )
            elif state.mode != "quiet":
                sys.stdout.write(
                    f"no audit-relevant changes since {diff_base}; "
                    f"{len(selection.changed_files)} file(s) considered.\n"
                )
            return
        requested_modules = sorted(selection.modules)

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
                module_concurrency=parallel_modules,
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
        module_concurrency=parallel_modules,
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
