"""Shared CLI test fixtures."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.app import build_app


@pytest.fixture
def runner() -> CliRunner:
    """Fresh CliRunner per test; mix_stderr=False so we can assert each stream."""

    return CliRunner(mix_stderr=False)


@pytest.fixture
def cli():
    """Fresh Typer app per test."""

    return build_app()


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    yield
    logging.getLogger("sentinelqa").handlers.clear()


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip CI-related env vars so tests don't auto-pick CI mode."""

    for var in ("SENTINEL_CI", "CI", "GITHUB_ACTIONS", "SENTINELQA_ASSERT_JSON_STDOUT"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def fresh_project(tmp_path: Path) -> Path:
    """An empty project root for init / lifecycle tests."""

    project = tmp_path / "fresh"
    project.mkdir()
    return project


def write_config(project_root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    """Helper: drop a minimal valid sentinel.config.yaml in ``project_root``."""

    config_path = project_root / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: test-app\n"
        "  framework: unknown\n"
        "  package_manager: unknown\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "    - 127.0.0.1\n",
        encoding="utf-8",
    )
    return config_path
