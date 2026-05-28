"""Unit tests for ``sentinel_cli.commands.generate_cmd`` helpers (task 07.06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.generator import BrittlenessWarning

from sentinel_cli.commands import generate_cmd
from sentinel_cli.state import GlobalState


def _state(mode: str = "human") -> GlobalState:
    return GlobalState(
        config_path=Path("x"),
        json=mode == "json",
        verbose=False,
        quiet=mode == "quiet",
        ci=False,
        no_color=False,
        dry_run=False,
    )


def test_emit_audit_failure_human(capsys: pytest.CaptureFixture[str]) -> None:
    warnings = (BrittlenessWarning(file="a.ts", line=3, column=5, message="brittle", snippet=""),)
    generate_cmd._emit_audit_failure(_state("human"), warnings)
    out = capsys.readouterr()
    assert "brittleness audit failed" in out.err
    assert "a.ts:3" in out.err


def test_emit_audit_failure_json(capsys: pytest.CaptureFixture[str]) -> None:
    warnings = (BrittlenessWarning(file="a.ts", line=1, column=1, message="x", snippet=""),)
    generate_cmd._emit_audit_failure(_state("json"), warnings)
    out = capsys.readouterr()
    # JSON mode emits a single object on stdout.
    import json as _json

    payload = _json.loads(out.out.strip())
    assert payload["audit_failed"] is True
    assert payload["warnings_count"] == 1


def test_tsc_check_skips_when_tsc_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert generate_cmd._tsc_check(tmp_path, _state()) is True


def test_tsc_check_returns_true_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tsc" if name == "tsc" else None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr=""
        ),
    )
    assert generate_cmd._tsc_check(tmp_path, _state()) is True


def test_tsc_check_handles_os_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tsc" if name == "tsc" else None)

    def boom(*args: object, **kwargs: object) -> object:
        raise OSError("permission denied")

    monkeypatch.setattr(subprocess, "run", boom)
    assert generate_cmd._tsc_check(tmp_path, _state()) is False


def test_resolve_credentials_returns_none_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.config.schema import RootConfig

    monkeypatch.delenv("SENTINEL_USER", raising=False)
    monkeypatch.delenv("SENTINEL_PASS", raising=False)
    config = RootConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "project": {"name": "x"},
            "target": {"base_url": "http://localhost", "allowed_hosts": ["localhost"]},
            "security": {"mode": "safe"},
            "auth": {
                "login_url": "http://localhost/login",
                "username_env": "SENTINEL_USER",
                "password_env": "SENTINEL_PASS",
            },
        }
    )
    assert generate_cmd._resolve_credentials(config) is None


def test_resolve_credentials_returns_object_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.config.schema import RootConfig

    monkeypatch.setenv("SENTINEL_USER", "alice")
    monkeypatch.setenv("SENTINEL_PASS", "secret")
    config = RootConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "project": {"name": "x"},
            "target": {"base_url": "http://localhost", "allowed_hosts": ["localhost"]},
            "security": {"mode": "safe"},
            "auth": {
                "login_url": "http://localhost/login",
                "username_env": "SENTINEL_USER",
                "password_env": "SENTINEL_PASS",
            },
        }
    )
    creds = generate_cmd._resolve_credentials(config)
    assert creds is not None
    assert creds.username == "alice"


def test_resolve_credentials_returns_none_when_auth_block_absent() -> None:
    from engine.config.schema import RootConfig

    config = RootConfig.model_validate(
        {
            "schema_version": "1.0.0",
            "project": {"name": "x"},
            "target": {"base_url": "http://localhost", "allowed_hosts": ["localhost"]},
            "security": {"mode": "safe"},
        }
    )
    assert generate_cmd._resolve_credentials(config) is None
