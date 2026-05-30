"""Subprocess-level smoke: the installed `sentinel` binary actually runs."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PYPROJECT = REPO_ROOT / "apps" / "cli" / "pyproject.toml"


def _expected_cli_version() -> str:
    """Read the canonical CLI version from `apps/cli/pyproject.toml`.

    Pinning this against the live pyproject — rather than hard-coding the
    string — means a version bump in the release-prep PR doesn't have to
    chase a stale literal here.
    """

    text = CLI_PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if match is None:
        pytest.fail(f'could not find `version = "…"` in {CLI_PYPROJECT}')
    return match.group(1)


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
    assert result.stdout.strip() == _expected_cli_version()


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
