"""`--version` prints the package version."""

from __future__ import annotations

import importlib.metadata as importlib_metadata

from typer.testing import CliRunner


def test_version_prints_pyproject_version(runner: CliRunner, cli) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0, result.output
    expected = importlib_metadata.version("sentinelqa-cli")
    assert result.stdout.strip() == expected
