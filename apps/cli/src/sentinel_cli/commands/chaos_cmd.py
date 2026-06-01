"""``sentinel chaos`` — run the ChaosModule via the lifecycle.

Replaces the stub. The command drives the full
:class:`RunLifecycle` restricted to the ``chaos`` module so the same
lifecycle steps (safety policy, artifact tree, reporter dispatch,
exit-code mapping) run whether the user types ``sentinel audit`` or
``sentinel chaos``.

Safety boundary (our engineering rules, §39):

- No CLI flag in the aggressive / evasion / detection-bypass family
 exists. ``tests/security/test_chaos_no_evasion_flags.py`` greps
 the package + the CLI source for compound forbidden literals and
 introspects the Typer parameters.
- The module is OFF by default in ``modules.chaos``; the CLI runs it
 regardless because the operator explicitly invoked it — but every
 scenario still flows through :class:`SafetyPolicy.enforce`.

Exit codes:

- ``0`` — module produced no high/critical findings.
- ``1`` — quality gate failed (high/critical findings present, or the
 module is ``incomplete``).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
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
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.policy.audit_log import write_audit_entry

# Side-effect import — registers the chaos module with the
# process-wide registry. Same pattern as security / a11y / api.
import modules.chaos  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

KNOWN_CATEGORIES = ("network", "session", "ux", "data")


def _parse_csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def run_chaos(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    scenarios: Annotated[
        str | None,
        typer.Option(
            "--scenarios",
            help=(
                "Comma-separated subset of scenario IDs to run "
                "(e.g. 'network.api_500,ux.duplicate_submit'). "
                "Defaults to every config-enabled scenario."
            ),
        ),
    ] = None,
    categories: Annotated[
        str | None,
        typer.Option(
            "--categories",
            help=(
                "Comma-separated category subset "
                f"({','.join(KNOWN_CATEGORIES)}). "
                "Defaults to every config-enabled category."
            ),
        ),
    ] = None,
    flows: Annotated[
        str | None,
        typer.Option(
            "--flows",
            help=(
                "Comma-separated flow names. When set, only events "
                "matching one of these flow values are kept."
            ),
        ),
    ] = None,
    events_path: Annotated[
        Path | None,
        typer.Option(
            "--events",
            help=(
                "Path to a JSONL chaos-events log. Defaults to "
                "<run-dir>/chaos/events.jsonl (written by the TS chaos helpers)."
            ),
        ),
    ] = None,
) -> None:
    """Run the chaos module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel chaos: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    parsed_categories = _parse_csv(categories)
    unknown = [c for c in parsed_categories if c not in KNOWN_CATEGORIES]
    if unknown:
        sys.stderr.write(
            f"sentinel chaos: unknown category/categories {sorted(unknown)!r}. "
            f"Known categories: {','.join(KNOWN_CATEGORIES)}.\n"
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    parsed_scenarios = _parse_csv(scenarios)
    parsed_flows = _parse_csv(flows)

    artifacts_root = Path(".sentinel") / "runs"

    module_options: dict[str, Any] = {
        "enabled_categories": parsed_categories,
        "enabled_scenarios": parsed_scenarios,
        "flows": parsed_flows,
        "events_path": events_path,
    }

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["chaos"],
        ci=state.ci,
        module_options={"chaos": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next((m for m in typed_results if m.name == "chaos"), None)
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "chaos"),
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
            "event": "chaos.cli.complete",
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
                    "command": "chaos",
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


__all__ = ["KNOWN_CATEGORIES", "run_chaos"]
