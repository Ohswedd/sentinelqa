"""``sentinel security`` — run the SecurityModule via the lifecycle.

Replaces the stub. The command drives the full
:class:`RunLifecycle` restricted to the ``security`` module so the
same lifecycle steps (safety policy, artifact tree, reporter dispatch,
exit-code mapping) run whether the user types ``sentinel audit`` or
``sentinel security``.

the engineering guidelines: dangerous probes (stored XSS, SQLi against
non-local hosts) require ``--mode authorized_destructive`` plus a
``--proof-of-authorization`` document. Without them the module
silently skips those checks (no fake completion — the result records
``skipped=True`` with the precise reason).

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

# Side-effect import — registers the security module with the
# process-wide registry. Same pattern as a11y / perf / functional.
import modules.security  # noqa: F401
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

KNOWN_CHECKS = (
    "headers",
    "cookies",
    "cors",
    "csrf",
    "xss_reflected",
    "xss_stored",
    "sqli",
    "idor",
    "frontend_secrets",
    "dependency_scan",
    "sast",
)


def run_security(
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
                "Comma-separated route subset (e.g. '/,/login,/admin'). "
                "Overrides config.security.routes."
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
    mode: Annotated[
        str | None,
        typer.Option(
            "--mode",
            help=(
                "safe | authorized_destructive. Overrides config.security.mode + "
                "config.target.mode."
            ),
        ),
    ] = None,
    proof_of_authorization: Annotated[
        Path | None,
        typer.Option(
            "--proof-of-authorization",
            help=(
                "Path to a proof-of-authorization YAML doc. Required for "
                "--mode authorized_destructive."
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
    """Run the safe security module via the canonical RunLifecycle."""

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel security: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    if url is not None:
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"base_url": url})}
        )

    if mode is not None:
        if mode not in {"safe", "authorized_destructive"}:
            sys.stderr.write(
                "sentinel security: --mode must be 'safe' or 'authorized_destructive'.\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)
        new_security = config.security.model_copy(update={"mode": mode})
        new_target = config.target.model_copy(update={"mode": mode})
        if proof_of_authorization is not None:
            new_target = new_target.model_copy(
                update={"proof_of_authorization": proof_of_authorization}
            )
        config = config.model_copy(update={"security": new_security, "target": new_target})
    elif proof_of_authorization is not None:
        config = config.model_copy(
            update={
                "target": config.target.model_copy(
                    update={"proof_of_authorization": proof_of_authorization}
                )
            }
        )

    parsed_routes: tuple[str, ...] = ()
    if routes is not None:
        parsed_routes = tuple(r.strip() for r in routes.split(",") if r.strip())
        if not parsed_routes:
            sys.stderr.write("sentinel security: --routes resolved to an empty list.\n")
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    parsed_checks: tuple[str, ...] = ()
    if checks is not None:
        parsed_checks = tuple(c.strip() for c in checks.split(",") if c.strip())
        unknown = [c for c in parsed_checks if c not in KNOWN_CHECKS]
        if unknown:
            sys.stderr.write(
                f"sentinel security: unknown check(s) {sorted(unknown)!r}. "
                f"Known checks: {','.join(KNOWN_CHECKS)}.\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    fallback_routes: tuple[str, ...] = ()
    if not parsed_routes and discovery is None and not config.security.routes:
        fallback_routes = ("/",)

    module_options: dict[str, Any] = {
        "routes": parsed_routes or fallback_routes,
        "discovery_path": discovery,
        "enabled_checks": parsed_checks,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["security"],
        ci=state.ci,
        module_options={"security": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "security"),
        None,
    )
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "security"),
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
            "event": "security.complete",
            "run_id": test_run.id,
            "module_status": raw_status,
            "findings": len(findings),
            "high_or_critical": high_or_critical,
            "exit_code": exit_code,
            "mode": config.security.mode,
        },
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "security",
                    "run_id": test_run.id,
                    "status": test_run.status,
                    "module_status": raw_status,
                    "findings": len(findings),
                    "high_or_critical": high_or_critical,
                    "exit_code": exit_code,
                    "mode": config.security.mode,
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"run_id : {test_run.id}\n"
            f"run_status : {test_run.status}\n"
            f"module_status : {raw_status}\n"
            f"findings : {len(findings)}\n"
            f"high_or_critical : {high_or_critical}\n"
            f"mode : {config.security.mode}\n"
        )

    raise typer.Exit(code=exit_code)


__all__ = ["run_security", "KNOWN_CHECKS"]
