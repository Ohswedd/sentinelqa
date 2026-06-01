"""`sentinel --help` registers every documented top-level command."""

from __future__ import annotations

import re

from typer.testing import CliRunner

# Every command name must appear in --help output.
EXPECTED_COMMANDS = (
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

# Rich emits SGR escapes (ESC[...m) around command names when the runner
# thinks it's writing to a TTY; that breaks `\b<cmd>\b` regex matching
# because the byte immediately before `init` is `m`, a word character.
# Strip them before asserting.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_help_lists_every_top_level_command(runner: CliRunner, cli) -> None:
    result = runner.invoke(cli, ["--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    output = _strip_ansi(result.stdout)
    for command in EXPECTED_COMMANDS:
        assert re.search(
            rf"\b{re.escape(command)}\b", output
        ), f"Command {command!r} missing from --help output:\n{output}"


def test_help_no_args_shows_help(runner: CliRunner, cli) -> None:
    # `no_args_is_help=True` — invoking with no args should print help and exit.
    result = runner.invoke(cli, [], terminal_width=120)
    assert result.exit_code == 0
    output = _strip_ansi(result.stdout)
    assert "Usage:" in output or "Commands" in output
