"""``sentinel supply-chain`` — run the SupplyChainModule (Phase 33).

Replaces the Phase 02 stub. The top-level command drives the full
:class:`RunLifecycle` restricted to the ``supply_chain`` module so the
canonical lifecycle steps (safety policy, artifact tree, reporter
dispatch, exit-code mapping) run whether the user types
``sentinel audit`` or ``sentinel supply-chain``.

Two sub-surfaces are exposed for callers that want to drive individual
stages without the full module:

- ``sentinel supply-chain sbom --out <dir>`` — emit a CycloneDX SBOM
  to ``<dir>`` without running OSV / freshness / etc.
- ``sentinel supply-chain osv --sbom <path>`` — run an OSV lookup
  against an existing ``sbom/index.json``.

Exit codes (CLAUDE §13):

- ``0`` — no high/critical findings.
- ``1`` — quality gate failed (high/critical, or module incomplete).
- ``2`` — invalid config or CLI usage.
- ``4`` — safety policy blocked the target.
- ``5`` — required tool missing (none for the top-level command;
  the container check downgrades to ``skipped`` instead).
- ``6`` — runner failed to execute.
"""

from __future__ import annotations

import json
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

# Side-effect import — registers the supply_chain module.
import modules.supply_chain  # noqa: F401
from modules.supply_chain.osv import run_osv_lookup_from_sbom
from modules.supply_chain.sbom import build_sbom
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

KNOWN_CHECKS = (
    "sbom",
    "osv",
    "freshness",
    "postinstall",
    "container",
    "licenses",
)


supply_chain_app = typer.Typer(
    name="supply-chain",
    help=(
        "Supply-Chain & Dependency Audit (Phase 33, the documentation.3, ADR-0045). "
        "Generates a CycloneDX 1.5 SBOM, queries OSV for known CVEs, "
        "checks lockfile freshness + manifest drift, scans postinstall "
        "hooks, optionally scans a configured container image, and "
        "audits SPDX licenses."
    ),
    no_args_is_help=False,
    invoke_without_command=True,
)


@supply_chain_app.callback()
def run_supply_chain(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override target.base_url for this run."),
    ] = None,
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Directory to scan. Defaults to the current working directory.",
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
    container_image: Annotated[
        str | None,
        typer.Option(
            "--container-image",
            help=(
                "Override policy.supply_chain.container.image for this "
                "run. Without an image (and no config value), the "
                "container check is skipped."
            ),
        ),
    ] = None,
) -> None:
    """Top-level audit; invokes the canonical RunLifecycle."""

    if ctx.invoked_subcommand is not None:
        # Sub-command will run on its own; bail without invoking the
        # full lifecycle.
        return

    state: GlobalState = ctx.obj

    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel supply-chain: {exc}\n")
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
                f"sentinel supply-chain: unknown check(s) {sorted(unknown)!r}. "
                f"Known checks: {','.join(KNOWN_CHECKS)}.\n"
            )
            raise typer.Exit(code=EXIT_CONFIG_ERROR)

    module_options: dict[str, Any] = {
        "project_root": project_root.resolve() if project_root else None,
        "enabled_checks": parsed_checks,
        "container_image": container_image,
    }

    artifacts_root = Path(".sentinel") / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(
        config,
        requested_modules=["supply_chain"],
        ci=state.ci,
        module_options={"supply_chain": module_options},
    )

    last_ctx = lifecycle.last_context
    typed_results = last_ctx.typed_module_results if last_ctx is not None else ()
    typed_module = next(
        (m for m in typed_results if m.name == "supply_chain"),
        None,
    )
    findings = typed_module.findings if typed_module is not None else ()
    high_or_critical = sum(1 for f in findings if f.severity in {"critical", "high"})

    module_outcome = None
    if last_ctx is not None:
        module_outcome = next(
            (o for o in last_ctx.module_outcomes if o.name == "supply_chain"),
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
            "event": "supply_chain.complete",
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
                    "command": "supply-chain",
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


# ---------------------------------------------------------------------------
# `sentinel supply-chain sbom`
# ---------------------------------------------------------------------------


@supply_chain_app.command("sbom", help="Emit a CycloneDX 1.5 SBOM (no OSV / freshness / etc.).")
def run_sbom(
    ctx: typer.Context,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Directory to write per-lockfile CycloneDX docs + index.json.",
        ),
    ],
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Directory to scan. Defaults to the current working directory.",
        ),
    ] = None,
) -> None:
    state: GlobalState = ctx.obj
    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel supply-chain sbom: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    project_root = (project_root or Path.cwd()).resolve()
    out = out.resolve()
    sbom = build_sbom(
        project_root=project_root,
        project_name=config.project.name,
        sbom_dir=out,
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "supply-chain.sbom",
                    "project": config.project.name,
                    "components": sbom.components_count,
                    "lockfiles": len(sbom.lockfiles),
                    "output_dir": str(out),
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"project       : {config.project.name}\n"
            f"lockfiles     : {len(sbom.lockfiles)}\n"
            f"components    : {sbom.components_count}\n"
            f"output_dir    : {out}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# `sentinel supply-chain osv`
# ---------------------------------------------------------------------------


@supply_chain_app.command(
    "osv",
    help=(
        "Run an OSV lookup against an existing SBOM index. Writes the "
        "report to stdout in JSON mode, or to <sbom_dir>/vulnerabilities.json otherwise."
    ),
)
def run_osv(
    ctx: typer.Context,
    sbom: Annotated[
        Path,
        typer.Option("--sbom", help="Path to a CycloneDX SBOM index.json."),
    ],
) -> None:
    state: GlobalState = ctx.obj
    try:
        config = load_config(state.config_path)
    except (FileNotFoundError, ConfigError) as exc:
        sys.stderr.write(f"sentinel supply-chain osv: {exc}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from exc

    sbom_path = sbom.resolve()
    if not sbom_path.is_file():
        sys.stderr.write(f"sentinel supply-chain osv: SBOM not found: {sbom_path}\n")
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    payload = json.loads(sbom_path.read_text(encoding="utf-8"))
    # Re-hydrate via the model so the run_osv_lookup_from_sbom contract holds.
    from modules.supply_chain.models import SbomDocument

    sbom_doc = SbomDocument.model_validate(payload)
    sc_cfg = config.policy.supply_chain
    report = run_osv_lookup_from_sbom(
        sbom=sbom_doc,
        api_base=sc_cfg.osv.api_base,
        rate_limit_rps=sc_cfg.osv.rate_limit_rps,
        enabled=sc_cfg.osv.enabled,
    )

    output_path = sbom_path.parent / "vulnerabilities.json"
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if state.mode == "json":
        with json_stdout() as emit:
            emit.emit(
                {
                    "command": "supply-chain.osv",
                    "components": report.components_count,
                    "vulnerabilities": sum(len(c.advisories) for c in report.vulnerabilities),
                    "skipped": report.skipped,
                    "output": str(output_path),
                }
            )
    elif state.mode != "quiet":
        sys.stdout.write(
            f"components       : {report.components_count}\n"
            f"vulnerabilities  : "
            f"{sum(len(c.advisories) for c in report.vulnerabilities)}\n"
            f"skipped          : {report.skipped}\n"
            f"output           : {output_path}\n"
        )

    raise typer.Exit(code=EXIT_SUCCESS)


__all__ = ["KNOWN_CHECKS", "supply_chain_app"]
