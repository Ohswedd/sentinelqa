"""Task 18.05 — `sentinel mcp` CLI surface."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.app import build_app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """Strip ANSI escape codes from CliRunner output (CI renders with rich
    formatting; local often doesn't)."""

    return _ANSI_RE.sub("", text)


def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\n"
        "project:\n"
        "  name: mcp-cli-test\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    return cfg


def test_mcp_command_appears_in_help() -> None:
    runner = CliRunner()
    result = runner.invoke(build_app(), ["--help"])
    assert result.exit_code == 0
    stdout = _plain(result.stdout)
    assert " mcp " in stdout
    assert "Phase 18" not in stdout  # the stub message is gone


def test_mcp_help_lists_options() -> None:
    runner = CliRunner()
    result = runner.invoke(build_app(), ["mcp", "--help"])
    assert result.exit_code == 0
    stdout = _plain(result.stdout)
    assert "--stdio" in stdout
    assert "--http" in stdout
    assert "--log-level" in stdout


def test_mcp_http_rejects_non_loopback_port_value_zero(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        ["--config", str(cfg), "mcp", "--http", "0"],
    )
    # 0 is out of [1, 65535] — refused by LoopbackHttpTransport.
    assert result.exit_code == 4


def test_mcp_http_rejects_out_of_range_port(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        ["--config", str(cfg), "mcp", "--http", "70000"],
    )
    assert result.exit_code == 4


def test_mcp_config_missing_does_not_crash(tmp_path: Path) -> None:
    """When the config path doesn't exist, the CLI falls back to defaults.

    The actual config error surfaces when a tool is invoked. The CLI
    itself starts the server with the SDK's default project state so
    `sentinel mcp` from a fresh checkout never raises at boot.
    """

    runner = CliRunner()
    missing = tmp_path / "absent.yaml"
    result = runner.invoke(
        build_app(),
        ["--config", str(missing), "mcp", "--http", "0"],
    )
    # --http 0 is rejected by LoopbackHttpTransport with exit 4; the
    # important assertion is that the missing-config check did NOT
    # raise — i.e. we reached the transport-builder step.
    assert result.exit_code == 4


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
def test_mcp_log_level_accepted(tmp_path: Path, level: str) -> None:
    runner = CliRunner()
    result = runner.invoke(build_app(), ["mcp", "--log-level", level, "--http", "0"])
    # --http=0 still refuses but we should reach the log-level parse
    # without complaint. Exit 4 confirms the option was accepted.
    assert result.exit_code == 4
