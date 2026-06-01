"""``sentinel api`` — run the ApiModule via the lifecycle.

Replaces the stub. The command drives the full
:class:`RunLifecycle` restricted to the ``api`` module so the
same lifecycle steps (safety policy, artifact tree, reporter dispatch,
exit-code mapping) run whether the user types ``sentinel audit`` or
``sentinel api``.

our engineering rules reminder: aggressive fuzzing is forbidden. No CLI flag
on this command enables it; the I/O-layer body-size cap in
:func:`modules.api.http_client.safe_request` enforces the same
guarantee.

Exit codes:

- ``0`` — module produced no high/critical findings.
- ``1`` — quality gate failed (high/critical findings present, or the
 module is ``incomplete``).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
- ``5`` — required dependency missing (none for ).
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

# Side-effect import — registers the api module with the
# process-wide registry. Same pattern as security / a11y / perf.
import modules.api  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

KNOWN_CHECKS = (
    "contract",
    "negative",
    "auth",
    "latency",
    "pagination",
    "error_shape",
    "backward_compat",
)


def run_api(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    openapi: Annotated[
        Path | None,
        typer.Option(
            "--openapi",
            help="Path to an OpenAPI 3.x JSON / YAML doc. Overrides config.api.openapi_path.",
        ),
    ] = None,
    graphql: Annotated[
        Path | None,
        typer.Option(
            "--graphql",
            help="Path to a GraphQL SDL file. Overrides config.api.graphql_path.",
        ),
    ] = None,
    discovery: Annotated[
        Path | None,
        typer.Option(
            "--discovery",
            help="Path to a discovery.json artifact whose routes to audit.",
        ),
    ] = None,
    diff_since: Annotated[
        str | None,
        typer.Option(
            "--diff-since",
            help=(
                "Diff today's API schema against the snapshot from the named "
                "run-id (looked up under .sentinel/runs/<id>/api/api-schema.json)."
            ),
        ),
    ] = None,
    checks: Annotated[
        str | None,
        typer.Option(
            "--checks",
            help=(
                "Comma-separated subset of checks to run. "
                f"Known: {','.join(KNOWN_CHECKS)}. Defaults to every "
                "config-enabled check."
            ),
        ),
    ] = None,
) -> None:
    """Run the API module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel api: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    parsed_checks: tuple[str, ...] = ()
    if checks is not None:
        parsed_checks = tuple(c.strip() for c in checks.split(",") if c.strip())
        unknown = [c for c in parsed_checks if c not in KNOWN_CHECKS]
        if unknown:
            sys.stderr.write(
                f"sentinel api: unknown check(s) {sorted(unknown)!r}. "
                f"Known checks: {','.join(KNOWN_CHECKS)}.\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    artifacts_root = Path(".sentinel") / "runs"

    module_options: dict[str, Any] = {
        "openapi_path": openapi,
        "graphql_path": graphql,
        "discovery_path": discovery,
        "enabled_checks": parsed_checks,
        "diff_since_run_id": diff_since,
        "artifacts_root": artifacts_root,
    }

    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["api"],
        ci=state.ci,
        module_options={"api": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next((m for m in typed_results if m.name == "api"), None)
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "api"),
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
            "event": "api.cli.complete",
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
                    "command": "api",
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


__all__ = ["KNOWN_CHECKS", "run_api"]
