# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Surface tests for `--install-completion` / `--show-completion`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sentinel_cli.app import build_app

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_help_advertises_install_completion() -> None:
    """The install command must be discoverable from `sentinel --help`."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    assert "--install-completion" in result.output


def test_help_advertises_show_completion() -> None:
    """`--show-completion` is the discovery escape hatch."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    assert "--show-completion" in result.output


def test_help_mentions_documentation_pointer() -> None:
    """The root help string carries the one-line install hint."""

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=120)
    assert result.exit_code == 0, result.output
    assert "Shell completions" in result.output


def test_completion_doc_exists_and_lists_every_shell() -> None:
    """docs/user/shell-completion.md must enumerate every supported shell."""

    doc = REPO_ROOT / "docs" / "user" / "shell-completion.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    for shell in ("bash", "zsh", "fish", "powershell"):
        assert (
            f"sentinel --install-completion {shell}" in text
        ), f"shell-completion.md missing install command for {shell!r}"
