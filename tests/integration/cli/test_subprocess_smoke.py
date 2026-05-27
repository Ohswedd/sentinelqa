"""Subprocess-level smoke: the installed `sentinel` binary actually runs."""

from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.fixture
def sentinel_bin() -> str:
    bin_path = shutil.which("sentinel")
    if bin_path is None:
        pytest.skip("`sentinel` console script not on PATH (run `uv pip install -e apps/cli`).")
    return bin_path


def test_sentinel_version(sentinel_bin: str) -> None:
    result = subprocess.run(
        [sentinel_bin, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.0.0"


def test_sentinel_help_lists_commands(sentinel_bin: str) -> None:
    result = subprocess.run(
        [sentinel_bin, "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for command in ("init", "doctor", "audit", "discover", "plan"):
        assert command in result.stdout
