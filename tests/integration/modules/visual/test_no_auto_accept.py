"""Integration: CI never auto-accepts.

The CLI-layer guard is exercised in :mod:`tests.integration.cli.test_visual`.
This module asserts the contract from the library side: the baseline
storage helpers can promote, but the CI guard sits in the CLI and is
the only place that mutates state — so we exercise both halves
together: with CI mode on, ``sentinel visual accept`` must fail; with
CI mode off, the same invocation succeeds and an audit-log entry is
recorded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


def _png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), (0, 0, 0)).save(path, format="PNG")


@pytest.fixture(autouse=True)
def _ensure_registered() -> None:
    from modules.visual import register_with_default_registry

    register_with_default_registry()


def test_ci_env_blocks_accept_even_without_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(tmp_path)
    current = tmp_path / "current"
    _png(current / "desktop" / "home.png")
    monkeypatch.setenv("SENTINEL_CI", "true")
    runner = CliRunner(mix_stderr=False)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            build_app(),
            ["visual", "accept", "--current", str(current), "--run-id", "RUN-AAAAAAAAAAAA"],
        )
    finally:
        os.chdir(cwd)
    assert result.exit_code == 4
    # No baseline should have been written.
    assert not (tmp_path / ".sentinel" / "baselines").exists()


def test_local_accept_with_no_ci_env_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(tmp_path)
    current = tmp_path / "current"
    _png(current / "desktop" / "home.png")
    for var in ("SENTINEL_CI", "CI", "GITHUB_ACTIONS"):
        monkeypatch.delenv(var, raising=False)
    runner = CliRunner(mix_stderr=False)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(
            build_app(),
            ["visual", "accept", "--current", str(current), "--run-id", "RUN-LOCALACCEPT"],
        )
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (tmp_path / ".sentinel" / "baselines" / "desktop" / "home.png").exists()
    # Audit-log entry recorded.
    audit_path = tmp_path / ".sentinel" / "runs" / "RUN-LOCALACCEPT" / "audit.log"
    assert audit_path.exists()
    payload = json.loads(audit_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert payload["event"] == "visual.accept"
    assert payload["run_id"] == "RUN-LOCALACCEPT"
