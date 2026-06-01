"""``sentinel visual`` — / the documentation visual-regression CLI.

Replaces the stub. Three subcommands:

- ``diff`` (default) — diff ``current/`` PNGs against baselines via
 the canonical :class:`RunLifecycle`.
- ``accept`` — promote ``current/`` PNGs into the baseline
 tree. Refused in CI (CLAUDE §29, §39): every CI-mode invocation of
 ``accept`` exits with :data:`EXIT_UNSAFE_TARGET` and writes an
 audit-log entry.
- ``capture`` — record an externally-supplied PNG tree as
 ``current/`` so a downstream ``diff`` can run. The capture
 pipeline (Playwright TS) is wired through the run-lifecycle's
 visual sub-tree; this subcommand wraps the bookkeeping so users
 can feed PNGs from another tool in the interim.

Exit codes (CLAUDE §13):

- ``0`` — no visual findings.
- ``1`` — quality gate failed (differ / size_mismatch / missing_current).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target OR CI-mode accept refused.
- ``6`` — module failed.
- ``7`` — internal error.
"""

from __future__ import annotations

import shutil
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
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.policy.audit_log import write_audit_entry

# Side-effect import — registers the visual module with the
# process-wide registry. Same pattern as a11y/security/llm_audit.
import modules.visual  # noqa: F401
from modules.visual.baselines import (
    load_index,
    promote_to_baseline,
    write_index,
)
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState, detect_ci_default

visual_app = typer.Typer(
    name="visual",
    help=(
        "Visual-regression checks (the documentation). Three subcommands: "
        "`diff` (default) compares captured PNGs vs baselines; "
        "`accept` promotes captures to baselines (refused in CI); "
        "`capture` records an externally-supplied PNG tree."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@visual_app.command("diff", help="Diff current PNGs against baselines.")
def diff_cmd(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    current_root: Annotated[
        Path | None,
        typer.Option(
            "--current",
            help=(
                "Directory tree of current-run PNGs "
                "(<viewport>/<route-slug>.png). Defaults to <run-dir>/visual/current."
            ),
        ),
    ] = None,
    baselines_dir: Annotated[
        Path | None,
        typer.Option(
            "--baselines",
            help="Override visual.baselines_dir for this invocation.",
        ),
    ] = None,
    viewports: Annotated[
        str | None,
        typer.Option(
            "--viewports",
            help="Comma-separated subset of configured viewport names.",
        ),
    ] = None,
    routes: Annotated[
        str | None,
        typer.Option(
            "--routes",
            help="Comma-separated subset of route slugs.",
        ),
    ] = None,
    threshold: Annotated[
        float | None,
        typer.Option(
            "--threshold",
            help="Override visual.threshold (0.0-1.0, fraction of differing pixels).",
            min=0.0,
            max=1.0,
        ),
    ] = None,
) -> None:
    """Diff captured PNGs against the baselines and exit with the lifecycle code."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel visual diff: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    module_options: dict[str, Any] = {
        "current_root": current_root,
        "baselines_dir": baselines_dir,
        "viewports": _parse_csv(viewports),
        "routes": _parse_csv(routes),
        "threshold": threshold,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["visual"],
        ci=state.ci,
        module_options={"visual": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next((m for m in typed_results if m.name == "visual"), None)
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})
    differing = sum(
        1
        for f in findings
        if f.category in {"visual_pixel_diff", "visual_size_mismatch", "visual_missing_current"}
    )

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "visual"),
            None,
        )
    raw_status = (
        typed_module.status
        if typed_module is not None
        else (module_outcome.status if module_outcome is not None else "skipped")
    )

    if test_run.status == "unsafe_blocked":
        exit_code = EXIT_UNSAFE_TARGET
    elif raw_status == "errored":
        exit_code = EXIT_TEST_EXECUTION_FAILED
    elif raw_status == "skipped":
        exit_code = EXIT_SUCCESS
    elif typed_module is None:
        exit_code = EXIT_RUNTIME_ERROR
    elif differing > 0 or high_or_critical > 0:
        exit_code = EXIT_QUALITY_GATE_FAILED
    else:
        exit_code = EXIT_SUCCESS

    audit_log_path = artifacts_root / test_run.id / "audit.log"
    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "visual.diff.complete",
            "run_id": test_run.id,
            "module_status": raw_status,
            "findings": len(findings),
            "high_or_critical": high_or_critical,
            "differing": differing,
            "exit_code": exit_code,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "visual.diff",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "module_status": raw_status,
                    "findings": len(findings),
                    "high_or_critical": high_or_critical,
                    "differing": differing,
                    "exit_code": exit_code,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id            : {test_run.id}\n"
            f"run_status        : {test_run.status}\n"
            f"module_status     : {raw_status}\n"
            f"findings          : {len(findings)}\n"
            f"high_or_critical  : {high_or_critical}\n"
            f"differing         : {differing}\n"
        )

    raise typer.Exit(code=exit_code)


@visual_app.command("accept", help="Promote current PNGs into the baseline tree.")
def accept_cmd(
    ctx: typer.Context,
    current_root: Annotated[
        Path,
        typer.Option(
            "--current",
            help=(
                "Directory tree of current-run PNGs to promote " "(<viewport>/<route-slug>.png)."
            ),
        ),
    ],
    baselines_dir: Annotated[
        Path | None,
        typer.Option(
            "--baselines",
            help="Override visual.baselines_dir for this invocation.",
        ),
    ] = None,
    viewports: Annotated[
        str | None,
        typer.Option("--viewports", help="Comma-separated subset of viewports."),
    ] = None,
    routes: Annotated[
        str | None,
        typer.Option("--routes", help="Comma-separated subset of route slugs."),
    ] = None,
    run_id: Annotated[
        str,
        typer.Option(
            "--run-id",
            help=(
                "Run id to attribute the acceptance to. Use the source run's id "
                "when accepting after a diff (so the index records who promoted)."
            ),
        ),
    ] = "RUN-LOCALACCEPTED",
) -> None:
    """Promote captured PNGs to baselines. Refused in CI mode."""

    state: GlobalState = ctx.obj
    # CI guard — uses state.ci (CLI flag) OR env vars. The CLI flag is
    # already auto-set from env vars in the root callback, but we re-check
    # the raw env vars here so `sentinel visual accept` refuses even when
    # the caller passes only the env (without `--ci`).
    if state.ci or detect_ci_default():
        sys.stderr.write(
            "sentinel visual accept: refusing to promote baselines in CI mode. "
            "Baselines must be reviewed by a human and accepted locally "
            "(CLAUDE §29).\n"
        )
        # Audit the refusal to the visual subdir so the operator has a
        # paper trail of every CI-blocked attempt.
        guard_log = (
            current_root.parent
            if current_root.exists()
            else Path(".sentinel") / "runs" / "RUN-CIACCEPTBLOCK"
        )
        guard_log.mkdir(parents=True, exist_ok=True)
        write_audit_entry(
            guard_log / "audit.log",
            {
                "decided_at": datetime.now(UTC).isoformat(),
                "event": "visual.accept.refused_ci",
                "current_root": str(current_root),
                "ci_env": detect_ci_default(),
                "ci_flag": state.ci,
            },
        )
        raise typer.Exit(code=EXIT_UNSAFE_TARGET)

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel visual accept: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    resolved_baselines = baselines_dir or config.visual.baselines_dir
    if not resolved_baselines.is_absolute():
        resolved_baselines = Path.cwd() / resolved_baselines

    if not current_root.exists() or not current_root.is_dir():
        sys.stderr.write(f"sentinel visual accept: --current {current_root} is not a directory.\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    viewport_filter = set(_parse_csv(viewports))
    route_filter = set(_parse_csv(routes))
    captured_at = datetime.now(UTC).isoformat()

    try:
        existing = load_index(resolved_baselines)
    except ValueError as exc:
        sys.stderr.write(f"sentinel visual accept: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    promoted: list[dict[str, Any]] = []
    for viewport_dir in sorted(current_root.iterdir()):
        if not viewport_dir.is_dir():
            continue
        if viewport_filter and viewport_dir.name not in viewport_filter:
            continue
        for png in sorted(viewport_dir.glob("*.png")):
            slug = png.stem
            if route_filter and slug not in route_filter:
                continue
            record = promote_to_baseline(
                baselines_dir=resolved_baselines,
                viewport=viewport_dir.name,
                route_slug=slug,
                source_png=png,
                captured_by_run_id=run_id,
                captured_at=captured_at,
            )
            existing[(record.viewport, record.route_slug)] = record
            promoted.append(
                {
                    "viewport": record.viewport,
                    "route_slug": record.route_slug,
                    "sha256": record.sha256,
                }
            )

    if not promoted:
        sys.stderr.write(
            "sentinel visual accept: no PNGs matched the viewport/route filter "
            f"under {current_root}.\n"
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    index_path = write_index(resolved_baselines, existing.values())

    audit_log_path = Path(".sentinel") / "runs" / run_id / "audit.log"
    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "visual.accept",
            "run_id": run_id,
            "baselines_dir": str(resolved_baselines),
            "promoted": promoted,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "visual.accept",
                    "run_id": run_id,
                    "baselines_dir": str(resolved_baselines),
                    "index": str(index_path),
                    "promoted": len(promoted),
                    "exit_code": EXIT_SUCCESS,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"baselines_dir : {resolved_baselines}\n"
            f"promoted      : {len(promoted)}\n"
            f"index         : {index_path}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


@visual_app.command("capture", help="Stage externally-supplied PNGs as the run's current/.")
def capture_cmd(
    ctx: typer.Context,
    source: Annotated[
        Path,
        typer.Option(
            "--from",
            help=(
                "Directory of PNGs to copy into the run's current tree. "
                "Layout: <source>/<viewport>/<route-slug>.png."
            ),
        ),
    ],
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run id whose visual/current to populate."),
    ],
    viewports: Annotated[
        str | None,
        typer.Option("--viewports", help="Comma-separated subset of viewports."),
    ] = None,
) -> None:
    """Copy PNGs from ``source`` into ``<run-dir>/visual/current/``."""

    state: GlobalState = ctx.obj
    if not source.exists() or not source.is_dir():
        sys.stderr.write(f"sentinel visual capture: --from {source} is not a directory.\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    dest_root = Path(".sentinel") / "runs" / run_id / "visual" / "current"
    dest_root.mkdir(parents=True, exist_ok=True)

    viewport_filter = set(_parse_csv(viewports))
    copied: list[str] = []
    for viewport_dir in sorted(source.iterdir()):
        if not viewport_dir.is_dir():
            continue
        if viewport_filter and viewport_dir.name not in viewport_filter:
            continue
        dest_viewport = dest_root / viewport_dir.name
        dest_viewport.mkdir(parents=True, exist_ok=True)
        for png in sorted(viewport_dir.glob("*.png")):
            dest = dest_viewport / png.name
            shutil.copyfile(png, dest)
            copied.append(f"{viewport_dir.name}/{png.name}")

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "visual.capture",
                    "run_id": run_id,
                    "dest": str(dest_root),
                    "copied": copied,
                    "exit_code": EXIT_SUCCESS,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id : {run_id}\n" f"dest   : {dest_root}\n" f"copied : {len(copied)}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


# Default callback so `sentinel visual` without args shows the typer
# help instead of crashing — Typer subapp behaviour is already to
# print help when no_args_is_help=True, no extra callback needed.
__all__ = ["accept_cmd", "capture_cmd", "diff_cmd", "visual_app"]
