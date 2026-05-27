"""`sentinel --help` registers every PRD §13.1 command (task 02.01)."""

from __future__ import annotations

import re

from typer.testing import CliRunner

# PRD §13.1 — every command name must appear in --help output.
PRD_COMMANDS = (
    "init",
    "doctor",
    "discover",
    "plan",
    "generate",
    "test",
    "audit",
    "functional",
    "api",
    "a11y",
    "perf",
    "visual",
    "security",
    "chaos",
    "llm-audit",
    "fix",
    "report",
    "ci",
    "mcp",
)


def test_help_lists_every_prd_command(runner: CliRunner, cli) -> None:
    result = runner.invoke(cli, ["--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    output = result.stdout
    for command in PRD_COMMANDS:
        assert re.search(
            rf"\b{re.escape(command)}\b", output
        ), f"Command {command!r} missing from --help output:\n{output}"


def test_help_no_args_shows_help(runner: CliRunner, cli) -> None:
    # `no_args_is_help=True` — invoking with no args should print help and exit.
    result = runner.invoke(cli, [], terminal_width=120)
    assert "Usage:" in result.stdout or "Commands" in result.stdout
