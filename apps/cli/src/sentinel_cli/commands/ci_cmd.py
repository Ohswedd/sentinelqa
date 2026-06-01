"""`sentinel ci` — replacement for the Phase-02 stub.

Implements the our product spec contract: a thin preset over the audit lifecycle
that selects modules, applies a Playwright ``--grep`` tag filter, and
optionally raises the quality-gate floor.

This command does not re-implement the lifecycle — it only translates
``--mode`` / ``--diff`` / ``--fail-under`` into inputs the existing
:class:`engine.orchestrator.run_lifecycle.RunLifecycle` already accepts.
The mode metadata is persisted as ``ci.json`` in the run directory so
downstream tools (PR comment, Slack, HTML report) can introspect what
preset ran.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from engine.ci.diff_aware import DiffSelection, select_from_git
from engine.ci.modes import (
    CI_MODES,
    DEFAULT_CI_MODE,
    CiMode,
    InvalidCiModeError,
    apply_mode,
)
from engine.config.loader import load_config
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

CI_METADATA_SCHEMA_VERSION = "1"
"""Schema version for the ``ci.json`` sidecar written by this command."""


def run_ci(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option(
            "--url",
            help="Override `target.base_url` for this run.",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help=(
                "CI mode preset (the documentation): " "fast | standard | full | nightly | release."
            ),
        ),
    ] = DEFAULT_CI_MODE,
    diff: Annotated[
        str | None,
        typer.Option(
            "--diff",
            help=(
                "Git diff range (e.g. `origin/main...HEAD`) for impacted-tests "
                "selection. Translation lives in `engine.ci.diff_aware` "
                "(Phase 17.05)."
            ),
        ),
    ] = None,
    fail_under: Annotated[
        int | None,
        typer.Option(
            "--fail-under",
            help="Override policy.min_quality_score for the run.",
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
    grep: Annotated[
        str | None,
        typer.Option(
            "--grep",
            help=(
                "Additional Playwright `--grep` filter applied on top of the "
                "mode's tag filter. AND-combined via `(<mode>).*<grep>`."
            ),
        ),
    ] = None,
) -> None:
    """Run the audit in CI mode."""

    state: GlobalState = ctx.obj

    if mode not in CI_MODES:
        raise InvalidCiModeError(mode=mode)
    # The literal check above narrows the runtime value; mypy can't infer that
    # so we re-cast for the `apply_mode` call.
    resolved_mode: CiMode = mode  # type: ignore[assignment]

    cfg = load_config(state.config_path)
    if url is not None:
        cfg = cfg.model_copy(update={"target": cfg.target.model_copy(update={"base_url": url})})

    effective_cfg, plan = apply_mode(cfg, mode=resolved_mode, fail_under=fail_under)

    diff_selection: DiffSelection | None = None
    if diff:
        diff_selection = _resolve_diff_selection(diff_range=diff)

    diff_grep = diff_selection.grep() if diff_selection else None
    requested_modules = list(plan.modules) if plan.modules else None
    if diff_selection is not None and diff_selection.fallback_to_full:
        # Diff is too broad → fall back to the full module set the user
        # has configured. This is the "many-file fallback" required by
        # the task acceptance criteria.
        from engine.ci.modes import enabled_modules

        requested_modules = list(enabled_modules(effective_cfg.modules))

    module_options = _build_module_options(
        plan_grep=plan.grep,
        user_grep=grep,
        diff_grep=diff_grep,
    )

    artifacts_root = output if output is not None else Path(".sentinel") / "runs"

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        effective_cfg,
        requested_modules=requested_modules,
        dry_run=state.dry_run,
        ci=True,  # `sentinel ci` always forces CI mode.
        module_options=module_options,
    )

    last_context = lifecycle.last_context
    run_dir = (
        last_context.artifacts.root
        if last_context is not None and last_context.artifacts is not None
        else None
    )
    if run_dir is not None:
        _write_ci_metadata(
            run_dir=run_dir,
            mode=resolved_mode,
            diff=diff,
            fail_under=fail_under,
            plan_dict=plan.to_dict(),
            user_grep=grep,
            diff_selection=diff_selection,
        )

    exit_code = _status_to_exit_code(test_run.status)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "ci",
                    "mode": mode,
                    "diff": diff,
                    "fail_under": fail_under,
                    "modules": list(plan.modules),
                    "grep": plan.grep,
                    "user_grep": grep,
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "modules_run": list(test_run.modules_run),
                    "started_at": test_run.started_at.isoformat(),
                    "finished_at": (
                        test_run.finished_at.isoformat() if test_run.finished_at else None
                    ),
                    "ci_metadata_path": (str(run_dir / "ci.json") if run_dir is not None else None),
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id   : {test_run.id}\n"
            f"mode     : {mode}\n"
            f"modules  : {', '.join(plan.modules) or '(none)'}\n"
            f"grep     : {plan.grep or '(none)'}\n"
            f"status   : {test_run.status}\n"
        )

    if exit_code != EXIT_SUCCESS:
        raise typer.Exit(code=exit_code)


def _build_module_options(
    *,
    plan_grep: str | None,
    user_grep: str | None,
    diff_grep: str | None = None,
) -> dict[str, dict[str, object]]:
    """Translate the mode's tag filter into the lifecycle's options channel.

    The functional module is the only module that consumes a ``grep`` —
    other modules ignore unknown option keys.

    The diff-aware tag set is OR-combined with the mode preset because
    impacted tags expand coverage (we never want a small diff to drop
    the mode's required gates).
    """

    base_grep = _or_grep(plan_grep, diff_grep)
    combined_grep = _combine_grep(mode_grep=base_grep, user_grep=user_grep)
    if combined_grep is None:
        return {}
    return {"functional": {"grep": combined_grep}}


def _or_grep(*alternatives: str | None) -> str | None:
    """OR-combine non-empty Playwright tag-filter expressions."""

    non_empty = [a for a in alternatives if a]
    if not non_empty:
        return None
    if len(non_empty) == 1:
        return non_empty[0]
    return "|".join(non_empty)


def _combine_grep(*, mode_grep: str | None, user_grep: str | None) -> str | None:
    """AND-combine ``mode_grep`` and ``user_grep`` into a single Playwright filter."""

    if mode_grep is None and user_grep is None:
        return None
    if mode_grep is None:
        return user_grep
    if user_grep is None:
        return mode_grep
    return f"({mode_grep}).*{user_grep}"


def _resolve_diff_selection(*, diff_range: str) -> DiffSelection:
    """Compute the diff selection via ``git diff --name-only``.

    Errors are converted to typed CLI errors so the caller surfaces the
    canonical exit-code grid.
    """

    from engine.errors.base import ConfigError, DependencyMissingError

    try:
        return select_from_git(diff_range=diff_range, repo_root=Path.cwd())
    except FileNotFoundError as exc:
        raise DependencyMissingError(
            "git binary not found; cannot resolve --diff range.",
            technical_context={"diff_range": diff_range},
        ) from exc
    except ValueError as exc:
        raise ConfigError(detail=str(exc)) from exc


def _write_ci_metadata(
    *,
    run_dir: Path,
    mode: CiMode,
    diff: str | None,
    fail_under: int | None,
    plan_dict: dict[str, object],
    user_grep: str | None,
    diff_selection: DiffSelection | None = None,
) -> Path:
    """Write the deterministic ``ci.json`` sidecar."""

    payload: dict[str, object] = {
        "schema_version": CI_METADATA_SCHEMA_VERSION,
        "mode": mode,
        "diff_range": diff,
        "fail_under_override": fail_under,
        "user_grep": user_grep,
        "modules": plan_dict.get("modules", []),
        "grep": plan_dict.get("grep"),
        "policy_overrides": plan_dict.get("policy_overrides", {}),
        "extras": plan_dict.get("extras", {}),
        "diff_selection": diff_selection.to_dict() if diff_selection is not None else None,
        "written_at": datetime.now(UTC).isoformat(),
    }
    target = run_dir / "ci.json"
    blob = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    target.write_text(blob, encoding="utf-8")
    return target


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
        return EXIT_TEST_EXECUTION_FAILED
    return EXIT_CONFIG_ERROR


__all__ = ["CI_METADATA_SCHEMA_VERSION", "run_ci"]
