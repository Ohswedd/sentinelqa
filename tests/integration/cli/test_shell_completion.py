# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Surface tests for `--install-completion` / `--show-completion`."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from sentinel_cli.app import build_app

REPO_ROOT = Path(__file__).resolve().parents[3]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _strip(output: str) -> str:
    """Strip ANSI escapes and collapse Rich's panel-wrap whitespace.

    Rich may break long option names across lines when the rendered
    width is narrow (CI runners often report 80 cols even when Click
    is told otherwise). Collapsing trailing-pad + leading-pad pairs
    re-joins those splits so substring assertions are stable.
    """

    stripped = _ANSI.sub("", output)
    # Re-join lines that Rich wrapped inside an option-column box.
    stripped = re.sub(r"-\s*\n\s*│?\s*", "-", stripped)
    return re.sub(r"\n\s*│\s*", " ", stripped)


def test_help_advertises_install_completion() -> None:
    """The install command must be discoverable from `sentinel --help`."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert result.exit_code == 0, result.output
    assert "--install-completion" in _strip(result.output)


def test_help_advertises_show_completion() -> None:
    """`--show-completion` is the discovery escape hatch."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert result.exit_code == 0, result.output
    assert "--show-completion" in _strip(result.output)


def test_help_mentions_documentation_pointer() -> None:
    """The root help string carries the one-line install hint."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert result.exit_code == 0, result.output
    assert "Shell completions" in _strip(result.output)


def test_completion_doc_exists_and_lists_every_shell() -> None:
    """docs/user/shell-completion.md must enumerate every supported shell."""

    doc = REPO_ROOT / "docs" / "user" / "shell-completion.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    for shell in ("bash", "zsh", "fish", "powershell"):
        assert (
            f"sentinel --install-completion {shell}" in text
        ), f"shell-completion.md missing install command for {shell!r}"
