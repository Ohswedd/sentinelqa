"""Typer application factory (our product spec, our engineering rules).

The CLI is built as a function (`build_app`) so tests can construct
isolated instances. Module-level `app` is what the console script and
``python -m sentinel_cli`` use.

Most commands are stubs that exit code 7 until their phase ships. The
stubs are NOT silent — they print a single line naming the future phase
so users always know where the work landed.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path
from typing import Annotated, Final

import typer

from sentinel_cli.commands import (
    a11y_cmd,
    api_cmd,
    audit_cmd,
    auth_cmd,
    chaos_cmd,
    ci_cmd,
    discover_cmd,
    doctor_cmd,
    fix_cmd,
    functional_cmd,
    generate_cmd,
    init_cmd,
    llm_audit_cmd,
    llm_cmd,
    mcp_cmd,
    perf_cmd,
    plan_cmd,
    plugins_cmd,
    report_cmd,
    security_cmd,
    stubs,
    supply_chain_cmd,
    test_cmd,
    visual_cmd,
)
from sentinel_cli.state import GlobalState, detect_ci_default

# Commands stubbed-out in. Each entry binds (command_name,
# future_phase, one_line_help). Lifecycle commands that actually do
# something in (`init`, `doctor`, `audit`) are NOT here.
# replaces the `discover` stub. replaces the `chaos` stub.
_STUB_COMMANDS: Final[tuple[tuple[str, str, str], ...]] = ()


def _version_string() -> str:
    """Resolve the CLI version from package metadata."""

    try:
        return importlib_metadata.version("sentinelqa-cli")
    except importlib_metadata.PackageNotFoundError:
        return "0.0.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_version_string())
        raise typer.Exit(code=0)


def build_app() -> typer.Typer:
    """Construct the Typer app.

    Tests call this to get a fresh instance each time; production uses
    the module-level :data:`app` constant.
    """

    cli = typer.Typer(
        name="sentinel",
        help=(
            "SentinelQA — Playwright-native release-confidence engine.\n\n"
            "Run `sentinel doctor` first; then `sentinel audit --url ...`."
        ),
        no_args_is_help=True,
        add_completion=False,
        pretty_exceptions_enable=False,
    )

    @cli.callback()
    def _root(  # type: ignore[unused-ignore]
        ctx: typer.Context,
        config: Annotated[
            Path,
            typer.Option(
                "--config",
                "-c",
                help="Path to sentinel.config.yaml.",
                envvar="SENTINEL_CONFIG",
            ),
        ] = Path("sentinel.config.yaml"),
        json_mode: Annotated[
            bool,
            typer.Option(
                "--json",
                help="Emit only machine-readable JSON on stdout (CLAUDE §13).",
            ),
        ] = False,
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Increase log verbosity."),
        ] = False,
        quiet: Annotated[
            bool,
            typer.Option("--quiet", "-q", help="Emit nothing on success."),
        ] = False,
        ci: Annotated[
            bool,
            typer.Option(
                "--ci/--no-ci",
                help="Run in CI mode (no prompts, fail-fast, JSON output, deterministic).",
            ),
        ] = False,
        no_color: Annotated[
            bool,
            typer.Option(
                "--no-color",
                help="Disable ANSI color output (forced off in --json / --ci).",
            ),
        ] = False,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Build the execution plan but do not execute modules.",
            ),
        ] = False,
        version: Annotated[
            bool,
            typer.Option(
                "--version",
                callback=_version_callback,
                is_eager=True,
                help="Print SentinelQA CLI version and exit.",
            ),
        ] = False,
    ) -> None:
        """Configure shared CLI state.

        The root callback runs before every subcommand; it builds the
        :class:`GlobalState` we stash on ``ctx.obj`` and configures
        logging accordingly.
        """

        del version  # consumed by the eager callback

        # CI mode auto-detects from env vars (CLAUDE §39).
        effective_ci = ci or detect_ci_default()

        state = GlobalState(
            config_path=config,
            json=json_mode,
            verbose=verbose,
            quiet=quiet,
            ci=effective_ci,
            no_color=no_color or json_mode or effective_ci,
            dry_run=dry_run,
        )
        ctx.obj = state

        # Defer the actual logging configuration to main() so tests can
        # exercise the app without polluting global handlers. Subcommands
        # that need a logger pull `engine.get_logger(...)` directly.

    cli.command(name="init", help="Scaffold sentinel.config.yaml, CI workflow, and runtime dirs.")(
        init_cmd.run_init
    )
    cli.command(name="doctor", help="Check env, config, Playwright, and target reachability.")(
        doctor_cmd.run_doctor
    )
    cli.command(name="audit", help="Run the full audit lifecycle against the target.")(
        audit_cmd.run_audit
    )
    cli.command(
        name="discover",
        help="Crawl the target, build the discovery graph + risk map, write artifacts.",
    )(discover_cmd.run_discover)
    cli.command(
        name="plan",
        help="Build a deterministic test plan (optional LLM augment) from discovery + risk.",
    )(plan_cmd.run_plan)
    cli.command(
        name="generate",
        help="Generate Playwright specs, page objects, and fixtures from the plan.",
    )(generate_cmd.run_generate)
    cli.command(
        name="test",
        help="Run generated tests via the Playwright runner (local or Docker).",
    )(test_cmd.run_test)
    cli.command(
        name="functional",
        help="Run functional checks (login, CRUD, roles, etc.) via the lifecycle.",
    )(functional_cmd.run_functional)
    cli.command(
        name="a11y",
        help="Run accessibility checks (axe-core, keyboard, focus) via the lifecycle.",
    )(a11y_cmd.run_a11y)
    cli.command(
        name="perf",
        help=(
            "Run synthetic performance checks (LCP/CLS/INP/TTFB, API P95, "
            "JS bundle, long tasks, repeated-nav stability) via the lifecycle. "
            "All measurements are lab synthetic (CLAUDE §27), not RUM."
        ),
    )(perf_cmd.run_perf)
    cli.command(
        name="security",
        help=(
            "Run safe security checks (headers, cookies, CORS, CSRF, reflected "
            "XSS, IDOR, frontend secrets, dep-scan, optional SAST). Dangerous "
            "probes require --mode authorized_destructive + --proof-of-authorization."
        ),
    )(security_cmd.run_security)
    cli.command(
        name="api",
        help=(
            "Run API contract / negative / auth / pagination / error-shape / "
            "backward-compat checks (Phase 22, the documentation). Aggressive fuzzing "
            "is forbidden; payload sizes are clamped at the "
            "I/O layer regardless of config."
        ),
    )(api_cmd.run_api)
    cli.command(
        name="chaos",
        help=(
            "Run safe chaos / adversarial scenarios (Phase 23, the documentation): "
            "network (slow_3g / offline / api_500 / api_timeout), session "
            "(expired token / missing permissions), UX (duplicate submit, "
            "double-click race, back-forward, refresh mid-flow), data "
            "(empty / large datasets, storage corruption). The module is "
            "off by default; --scenarios / --categories subset the run. "
            "No aggressive / evasion flags exist."
        ),
    )(chaos_cmd.run_chaos)
    cli.command(
        name="report",
        help=(
            "Re-render reports for a completed run (HTML / JSON / SARIF / "
            "JUnit / Markdown) or explain its quality score (--explain-score). "
            "Reads from `.sentinel/runs/<run-id>/`; no module re-execution."
        ),
    )(report_cmd.run_report)
    cli.command(
        name="ci",
        help=(
            "Run the audit in CI mode: preset modules + tag "
            "filter + policy overrides per --mode "
            "(fast/standard/full/nightly/release)."
        ),
    )(ci_cmd.run_ci)
    cli.command(
        name="mcp",
        help=(
            "Start the SentinelQA MCP server (ADR-0023). Speaks the MCP "
            "stdio transport by default; pass --http <PORT> for a local "
            "loopback debug loop."
        ),
    )(mcp_cmd.run_mcp)
    cli.command(
        name="llm-audit",
        help=(
            "Run the LLM-code audit module (Phase 19, ADR-0024): dead "
            "buttons, fake routes/endpoints, mock data shipped, missing "
            "CRUD edges, UI-only auth, hardcoded credentials, localStorage "
            "secrets, loading/error-state gaps, validation mismatch, "
            "'coming soon' placeholders, console errors the UI ignores."
        ),
    )(llm_audit_cmd.run_llm_audit)
    cli.command(
        name="fix",
        help=(
            "Apply or surface healer-proposed repairs from a completed "
            "run (Phase 20, ADR-0025). Default is review-only; use "
            "--apply safe|aggressive to apply approved proposals."
        ),
    )(fix_cmd.run_fix)
    cli.add_typer(
        visual_cmd.visual_app,
        name="visual",
        help=(
            "Visual-regression checks (Phase 21, the documentation). `visual diff` "
            "compares captured PNGs against baselines; `visual accept` "
            "promotes captures into the baseline tree (refused in CI); "
            "`visual capture` stages an external PNG tree."
        ),
    )
    cli.add_typer(
        plugins_cmd.plugins_app,
        name="plugins",
        help=(
            "Manage SentinelQA plugins (Phase 24, our product spec, ADR-0029). "
            "`plugins list` shows installed plugins; `plugins info` "
            "prints one manifest; `plugins validate` checks a "
            "standalone manifest file."
        ),
    )
    cli.add_typer(
        llm_cmd.llm_app,
        name="llm",
        help=(
            "Multi-provider LLM management (Phase 30, ADR-0042). `llm "
            "list` shows registered providers; `llm doctor` probes "
            "reachability; `llm price` prints per-model cost tables."
        ),
    )
    cli.add_typer(
        auth_cmd.auth_app,
        name="auth",
        help=(
            "Browser-authenticated audits (Phase 31, ADR-0043). `auth "
            "login` opens a real browser so the operator can sign in "
            "once; SentinelQA encrypts the session locally and replays "
            "it on later audits. `list` / `revoke` / `export` manage "
            "the vault."
        ),
    )
    cli.add_typer(
        supply_chain_cmd.supply_chain_app,
        name="supply-chain",
        help=(
            "Supply-Chain & Dependency Audit (Phase 33, the documentation.3, "
            "ADR-0045). Generates a CycloneDX 1.5 SBOM, queries OSV "
            "for known CVEs, checks lockfile freshness, scans "
            "postinstall hooks, scans a configured container image, "
            "and audits SPDX licenses."
        ),
    )

    for name, phase, summary in _STUB_COMMANDS:
        stubs.register_stub(cli, name=name, phase=phase, summary=summary)

    return cli


app = build_app()


__all__ = ["app", "build_app"]
