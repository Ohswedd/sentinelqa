"""Typer application factory (PRD §13, CLAUDE.md §13).

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

from sentinel_cli.commands import audit_cmd, discover_cmd, doctor_cmd, init_cmd, plan_cmd, stubs
from sentinel_cli.state import GlobalState, detect_ci_default

# Commands stubbed-out in Phase 02. Each entry binds (command_name,
# future_phase, one_line_help). Lifecycle commands that actually do
# something in Phase 02 (`init`, `doctor`, `audit`) are NOT here. Phase 05
# replaces the `discover` stub.
_STUB_COMMANDS: Final[tuple[tuple[str, str, str], ...]] = (
    ("generate", "07", "Generate Playwright specs from the plan."),
    ("test", "08", "Run generated tests via the Playwright runner."),
    ("functional", "10", "Run functional checks (login, CRUD, roles, etc.)."),
    ("api", "22", "Run API contract + negative-case checks."),
    ("a11y", "11", "Run accessibility checks (axe-core, keyboard, focus)."),
    ("perf", "12", "Run performance checks against configured budgets."),
    ("visual", "21", "Run visual-regression checks against baselines."),
    ("security", "13", "Run safe security checks (headers, cookies, CORS)."),
    ("chaos", "23", "Run chaos checks (slow net, offline, session expiry)."),
    ("llm-audit", "19", "Run LLM-code audit (dead buttons, fake routes, etc.)."),
    ("fix", "20", "Propose locator repairs and other safe self-healing fixes."),
    ("report", "15", "Render HTML / JSON / SARIF / JUnit reports."),
    ("ci", "17", "Run the audit in CI mode (fail-fast, deterministic, JSON)."),
    ("mcp", "18", "Run the SentinelQA MCP server (sentinel.* tools)."),
)


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

    for name, phase, summary in _STUB_COMMANDS:
        stubs.register_stub(cli, name=name, phase=phase, summary=summary)

    return cli


app = build_app()


__all__ = ["app", "build_app"]
