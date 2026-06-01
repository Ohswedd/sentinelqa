"""``sentinel perf`` — run the performance module via the lifecycle.

Replaces the stub. The command drives the full
:class:`RunLifecycle` restricted to the ``performance`` module so the
same lifecycle steps (safety policy, artifact tree, reporter dispatch,
exit-code mapping) run whether the user types ``sentinel audit`` or
``sentinel perf``.

CLAUDE §27 reminder: every output is labelled **synthetic** — these
are lab measurements, not Real-User Monitoring. The forbidden-phrase
guard in ``tests/security/test_synthetic_perf_labeling.py`` makes that
the law of the build.

Exit codes (CLAUDE §13):

- ``0`` — module produced no high/critical findings.
- ``1`` — quality gate failed (high/critical findings present, or the
 module is ``incomplete``).
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

# Side-effect import — registers the performance module with the
# process-wide registry. Same pattern as a11y / functional CLI commands.
import modules.performance  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_perf(
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
                "Overrides config.performance.routes."
            ),
        ),
    ] = None,
    samples: Annotated[
        int | None,
        typer.Option(
            "--samples",
            help=(
                "Per-route sample count for LCP/CLS/INP/TTFB (default: from "
                "config.performance.samples, normally 3)."
            ),
        ),
    ] = None,
    repeated_nav_samples: Annotated[
        int | None,
        typer.Option(
            "--repeated-nav-samples",
            help=(
                "Per-route repeated-navigation sample count for the memory-leak "
                "heuristic (default: from config.performance.repeated_nav_samples)."
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
    """Run the performance module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel perf: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    parsed_routes: tuple[str, ...] = ()
    if routes is not None:
        parsed_routes = tuple(r.strip() for r in routes.split(",") if r.strip())
        if not parsed_routes:
            sys.stderr.write("sentinel perf: --routes resolved to an empty list.\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    if samples is not None and samples < 1:
        sys.stderr.write("sentinel perf: --samples must be >= 1.\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)
    if repeated_nav_samples is not None and repeated_nav_samples < 2:
        sys.stderr.write("sentinel perf: --repeated-nav-samples must be >= 2.\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    # Resolve a fallback route set when the caller didn't pass --routes,
    # --discovery, or set `performance.routes` in config. The CLI is the
    # only context where guessing "/" is appropriate — `sentinel audit`
    # leaves the module to short-circuit when no route plan exists.
    fallback_routes: tuple[str, ...] = ()
    if not parsed_routes and discovery is None and not config.performance.routes:
        fallback_routes = ("/",)

    module_options: dict[str, Any] = {
        "routes": parsed_routes or fallback_routes,
        "discovery_path": discovery,
        "samples": samples,
        "repeated_nav_samples": repeated_nav_samples,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["performance"],
        ci=state.ci,
        module_options={"performance": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "performance"),
        None,
    )
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "performance"),
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
            "event": "perf.complete",
            "run_id": test_run.id,
            "module_status": raw_status,
            "findings": len(findings),
            "high_or_critical": high_or_critical,
            "exit_code": exit_code,
            "measurement_kind": "synthetic",
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "perf",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "module_status": raw_status,
                    "findings": len(findings),
                    "high_or_critical": high_or_critical,
                    "exit_code": exit_code,
                    "measurement_kind": "synthetic",
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id            : {test_run.id}\n"
            f"run_status        : {test_run.status}\n"
            f"module_status     : {raw_status}\n"
            f"findings          : {len(findings)}\n"
            f"high_or_critical  : {high_or_critical}\n"
            f"measurement_kind  : synthetic (lab; not Real-User Monitoring)\n"
        )

    raise typer.Exit(code=exit_code)


__all__ = ["run_perf"]
