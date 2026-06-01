"""``sentinel llm-audit`` — run the LLM-code audit module.

Replaces the stub. Drives the canonical
:class:`engine.orchestrator.run_lifecycle.RunLifecycle` restricted to
the ``llm_audit`` module so the lifecycle steps (safety policy,
artifact tree, reporter dispatch, exit-code mapping) run whether the
user types ``sentinel audit`` or ``sentinel llm-audit``.

Exit codes:

- ``0`` — no high/critical findings.
- ``1`` — quality gate failed (high/critical findings).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
- ``6`` — module failed.
- ``7`` — internal error (module factory missing).
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

# Side-effect import — registers the LLM-audit module with the
# process-wide registry. Same pattern used by every + module.
import modules.llm_audit  # noqa: F401
from modules.llm_audit.module import ALL_CHECKS
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_llm_audit(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    discovery: Annotated[
        Path | None,
        typer.Option(
            "--discovery",
            help=(
                "Path to a discovery.json artifact whose links / endpoints feed "
                "the cross-reference checks."
            ),
        ),
    ] = None,
    signals_root: Annotated[
        Path | None,
        typer.Option(
            "--signals",
            help=(
                "Directory containing optional runtime-signal JSON files "
                "(signals.json, source_files.json). Defaults to the run's "
                "`llm_audit/` sub-directory."
            ),
        ),
    ] = None,
    checks: Annotated[
        str | None,
        typer.Option(
            "--checks",
            help=(
                "Comma-separated subset of checks to run. Default: every check. "
                f"Allowed: {', '.join(ALL_CHECKS)}."
            ),
        ),
    ] = None,
    third_party_hosts: Annotated[
        str | None,
        typer.Option(
            "--third-party-hosts",
            help=(
                "Comma-separated host suffixes whose console output is filtered "
                "from console-error analysis (e.g. analytics / ads domains)."
            ),
        ),
    ] = None,
) -> None:
    """Run the LLM-code audit module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel llm-audit: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    parsed_checks: tuple[str, ...] = ()
    if checks is not None:
        parsed_checks = tuple(c.strip() for c in checks.split(",") if c.strip())
        if not parsed_checks:
            sys.stderr.write("sentinel llm-audit: --checks resolved to empty.\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)
        invalid = tuple(name for name in parsed_checks if name not in ALL_CHECKS)
        if invalid:
            sys.stderr.write(
                f"sentinel llm-audit: unknown check(s) {sorted(invalid)!r}. "
                f"Allowed: {ALL_CHECKS}\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    parsed_third_party: tuple[str, ...] = ()
    if third_party_hosts is not None:
        parsed_third_party = tuple(h.strip() for h in third_party_hosts.split(",") if h.strip())

    module_options: dict[str, Any] = {
        "discovery_path": discovery,
        "signals_root": signals_root,
        "checks": parsed_checks,
        "third_party_console_hosts": parsed_third_party,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["llm_audit"],
        ci=state.ci,
        module_options={"llm_audit": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "llm_audit"),
        None,
    )
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "llm_audit"),
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
        # No signals available means no defects observed; this is the
        # honest "we didn't find anything" answer, not an error.
        exit_code = EXIT_SUCCESS
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
            "event": "llm_audit.complete",
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
                    "command": "llm-audit",
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


__all__ = ["run_llm_audit"]
