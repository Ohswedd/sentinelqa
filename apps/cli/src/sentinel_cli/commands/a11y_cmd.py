"""``sentinel a11y`` — run the accessibility module via the lifecycle (Phase 11).

Replaces the Phase 02 stub. The command drives the full
:class:`RunLifecycle` restricted to the ``accessibility`` module so the
same lifecycle steps (safety policy, artifact tree, reporter dispatch,
exit-code mapping) run whether the user types ``sentinel audit`` or
``sentinel a11y``.

Exit codes (CLAUDE §13):

- ``0`` — module produced no high/critical findings.
- ``1`` — quality gate failed (high/critical findings present, or the
  module is `incomplete`).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
- ``5`` — sentinel-ts binary missing.
- ``6`` — runner failed to execute.
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
    EXIT_DEPENDENCY_MISSING,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.policy.audit_log import write_audit_entry

# Side-effect import — registers the accessibility module with the
# process-wide registry. The same pattern is used for `modules.functional`
# in the functional CLI command.
import modules.accessibility  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_a11y(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    routes: Annotated[
        str | None,
        typer.Option(
            "--routes",
            help=(
                "Comma-separated route subset (e.g. '/,/dashboard,/settings'). "
                "Overrides config.accessibility.routes."
            ),
        ),
    ] = None,
    axe_tags: Annotated[
        str | None,
        typer.Option(
            "--axe-tags",
            help=(
                "Comma-separated axe tags (e.g. 'wcag2a,wcag2aa'). "
                "Overrides config.accessibility.axe.tags."
            ),
        ),
    ] = None,
    discovery: Annotated[
        Path | None,
        typer.Option(
            "--discovery",
            help="Path to a discovery.json artifact whose routes to audit.",
        ),
    ] = None,
) -> None:
    """Run the accessibility module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel a11y: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    parsed_routes: tuple[str, ...] = ()
    if routes is not None:
        parsed_routes = tuple(r.strip() for r in routes.split(",") if r.strip())
        if not parsed_routes:
            sys.stderr.write("sentinel a11y: --routes resolved to an empty list.\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    parsed_tags: tuple[str, ...] | None = None
    if axe_tags is not None:
        parsed_tags = tuple(t.strip() for t in axe_tags.split(",") if t.strip())
        if not parsed_tags:
            sys.stderr.write("sentinel a11y: --axe-tags resolved to an empty list.\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    # Resolve a fallback route set when the caller didn't pass --routes,
    # --discovery, or set `accessibility.routes` in config. The CLI is the
    # only context where guessing "/" is appropriate — `sentinel audit`
    # leaves the module to short-circuit when no route plan exists.
    fallback_routes: tuple[str, ...] = ()
    if not parsed_routes and discovery is None and not config.accessibility.routes:
        fallback_routes = ("/",)

    module_options: dict[str, Any] = {
        "routes": parsed_routes or fallback_routes,
        "discovery_path": discovery,
        "axe_tags": parsed_tags,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["accessibility"],
        ci=state.ci,
        module_options={"accessibility": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "accessibility"),
        None,
    )
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    # When the module raised inside the orchestrator (e.g. sentinel-ts
    # missing or Chromium crash) we never get a typed result — the
    # orchestrator records the error on `module_outcomes` instead.
    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "accessibility"),
            None,
        )
    raw_status = (
        typed_module.status
        if typed_module is not None
        else (module_outcome.status if module_outcome is not None else "skipped")
    )
    error_text = ""
    if module_outcome is not None and module_outcome.error_message:
        error_text = module_outcome.error_message

    if test_run.status == "unsafe_blocked":
        exit_code = EXIT_UNSAFE_TARGET
    elif raw_status == "errored" and "sentinel-ts" in error_text:
        exit_code = EXIT_DEPENDENCY_MISSING
    elif raw_status == "errored":
        exit_code = EXIT_TEST_EXECUTION_FAILED
    elif raw_status == "incomplete":
        exit_code = EXIT_QUALITY_GATE_FAILED
    elif typed_module is None:
        # Module factory missing or returned a non-SentinelModule — both
        # configuration errors from the lifecycle's perspective.
        exit_code = EXIT_RUNTIME_ERROR
    elif high_or_critical > 0:
        exit_code = EXIT_QUALITY_GATE_FAILED
    else:
        exit_code = EXIT_SUCCESS

    audit_log_path = artifacts_root / test_run.id / "audit.log"
    write_audit_entry(
        audit_log_path,
        {
            "decided_at": datetime.now(UTC).isoformat(),
            "event": "a11y.complete",
            "run_id": test_run.id,
            "module_status": raw_status,
            "findings": len(findings),
            "high_or_critical": high_or_critical,
            "exit_code": exit_code,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "a11y",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "module_status": raw_status,
                    "findings": len(findings),
                    "high_or_critical": high_or_critical,
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
        )

    raise typer.Exit(code=exit_code)


__all__ = ["run_a11y"]
