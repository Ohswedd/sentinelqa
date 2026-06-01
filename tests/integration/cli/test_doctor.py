"""`sentinel doctor`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_SUCCESS,
    EXIT_UNSAFE_TARGET,
)
from typer.testing import CliRunner

from sentinel_cli.commands import doctor_cmd
from tests.integration.cli.conftest import write_config


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


@pytest.fixture
def happy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock subprocess + httpx so doctor sees a healthy machine."""

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        head = cmd[0] if cmd else ""
        tail = cmd[1] if len(cmd) > 1 else ""
        if head.endswith("node"):
            return _FakeCompletedProcess(stdout="v20.10.0\n")
        if head.endswith("npx") and tail == "playwright":
            return _FakeCompletedProcess(stdout="Version 1.49.0\n")
        return _FakeCompletedProcess(stdout="")

    monkeypatch.setattr(doctor_cmd.subprocess, "run", _fake_run)

    def _fake_which(name: str) -> str:
        return f"/usr/local/bin/{name}"

    monkeypatch.setattr(doctor_cmd.shutil, "which", _fake_which)

    import httpx

    class _FakeResp:
        status_code = 200

    def _fake_head(url, **kwargs):  # type: ignore[no-untyped-def]
        return _FakeResp()

    monkeypatch.setattr(httpx, "head", _fake_head)


def test_doctor_happy(runner: CliRunner, cli, fresh_project: Path, happy_env) -> None:
    write_config(fresh_project)
    result = runner.invoke(
        cli,
        ["--config", str(fresh_project / "sentinel.config.yaml"), "doctor"],
    )
    assert result.exit_code == EXIT_SUCCESS, result.stdout + result.stderr
    assert "overall: ok" in result.stdout


def test_doctor_missing_config_is_warn_only(
    runner: CliRunner, cli, fresh_project: Path, happy_env
) -> None:
    # No config written — doctor downgrades the missing config to a warning.
    result = runner.invoke(
        cli,
        ["--config", str(fresh_project / "sentinel.config.yaml"), "doctor"],
    )
    # Missing config → warn (spec: only fail if config is malformed).
    assert result.exit_code == EXIT_SUCCESS, result.stdout + result.stderr
    assert "config" in result.stdout
    assert "warn" in result.stdout or "WARN" in result.stdout or "[warn]" in result.stdout


def test_doctor_unsafe_target_exits_4(
    runner: CliRunner, cli, fresh_project: Path, happy_env
) -> None:
    # Pointing base_url at a public host that isn't allowlisted should hit
    # the safety check and exit with EXIT_UNSAFE_TARGET (4).
    config_path = fresh_project / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: bad\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: []\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        cli,
        ["--config", str(config_path), "doctor"],
    )
    assert result.exit_code == EXIT_UNSAFE_TARGET, result.output


def test_doctor_invalid_config_exits_2(
    runner: CliRunner, cli, fresh_project: Path, happy_env
) -> None:
    config_path = fresh_project / "sentinel.config.yaml"
    config_path.write_text("not: a, valid: schema: at all", encoding="utf-8")
    result = runner.invoke(
        cli,
        ["--config", str(config_path), "doctor"],
    )
    assert result.exit_code == EXIT_CONFIG_ERROR, result.output


def test_doctor_missing_env_var_exits_5(
    runner: CliRunner, cli, fresh_project: Path, happy_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SENTINEL_DOCTOR_PROBE_USER", raising=False)
    config_path = fresh_project / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "auth:\n"
        "  strategy: test_user\n"
        "  username_env: SENTINEL_DOCTOR_PROBE_USER\n"
        "  password_env: SENTINEL_DOCTOR_PROBE_PASS\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        cli,
        ["--config", str(config_path), "doctor"],
    )
    assert result.exit_code == EXIT_DEPENDENCY_MISSING, result.output


def test_doctor_json_output_is_valid_json(
    runner: CliRunner, cli, fresh_project: Path, happy_env
) -> None:
    write_config(fresh_project)
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "doctor",
        ],
    )
    assert result.exit_code == EXIT_SUCCESS, result.output
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["command"] == "doctor"
    assert payload["status"] == "ok"
    assert any(c["name"] == "config" for c in payload["checks"])
