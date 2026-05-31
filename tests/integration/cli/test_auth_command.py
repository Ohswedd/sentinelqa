"""CLI integration tests for ``sentinel auth`` (Phase 31 task 31.08)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from sentinel_cli.app import build_app

# All tests share an isolated vault root + a stub keyring backend so they
# do NOT touch the developer's real ~/.sentinel/auth or OS keyring.


@pytest.fixture(autouse=True)
def _isolate_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault_root = tmp_path / "vault"
    monkeypatch.setenv("SENTINEL_VAULT_ROOT", str(vault_root))
    monkeypatch.setenv("SENTINEL_VAULT_SALT_PATH", str(tmp_path / ".salt"))
    monkeypatch.setenv("SENTINEL_VAULT_PASSPHRASE", "test-only-passphrase-1234567890ab")
    # Audit log location for the standalone `sentinel auth …` commands.
    monkeypatch.setenv("HOME", str(tmp_path))


def _run(*args: str) -> Result:
    return CliRunner().invoke(build_app(), list(args))


def test_list_profiles_human() -> None:
    result = _run("auth", "list-profiles")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "claude-ai" in result.stdout
    assert "github-oauth" in result.stdout


def test_list_profiles_json() -> None:
    # ``--json`` is a root-level flag; it must come before the subcommand.
    result = _run("--json", "auth", "list-profiles")
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    names = {p["name"] for p in payload["profiles"]}
    assert {
        "claude-ai",
        "chatgpt-codex",
        "chatgpt-web",
        "github-oauth",
        "google-gemini",
        "google-oauth",
        "microsoft-entra",
        "mistral-le-chat",
    } <= names


def test_list_empty_vault_human() -> None:
    result = _run("auth", "list")
    assert result.exit_code == 0
    assert "No vault entries" in result.stdout


def test_list_empty_vault_json() -> None:
    result = _run("--json", "auth", "list")
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["count"] == 0


def test_login_in_ci_mode_rejected() -> None:
    # Use mix_stderr=False so we can introspect both streams cleanly.
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--ci",
            "auth",
            "login",
            "github-myorg",
            "--url",
            "https://github.com/login",
        ],
    )
    assert result.exit_code != 0
    combined = (result.stdout + result.stderr).lower()
    assert "ci" in combined


def test_login_unknown_profile_rejected() -> None:
    result = _run(
        "auth",
        "login",
        "x",
        "--url",
        "https://example.com/login",
        "--profile",
        "does-not-exist",
    )
    assert result.exit_code == 2


def test_login_invalid_browser_rejected() -> None:
    result = _run(
        "auth",
        "login",
        "x",
        "--url",
        "https://example.com/login",
        "--browser",
        "ie6",
    )
    assert result.exit_code == 2


def test_export_requires_acknowledge() -> None:
    result = _run(
        "auth",
        "export",
        "myorg",
        "--host",
        "example.com",
        "--out",
        "/tmp/should-not-be-written.json",
    )
    assert result.exit_code != 0
    assert not Path("/tmp/should-not-be-written.json").exists()


def test_export_in_ci_mode_rejected() -> None:
    result = _run(
        "--ci",
        "auth",
        "export",
        "myorg",
        "--host",
        "example.com",
        "--out",
        "/tmp/should-not-be-written.json",
        "--i-acknowledge",
    )
    assert result.exit_code != 0
    assert not Path("/tmp/should-not-be-written.json").exists()


def test_revoke_missing_name_or_host_rejected() -> None:
    result = _run("auth", "revoke")
    assert result.exit_code == 2


def test_revoke_all_requires_confirmation_input() -> None:
    # In non-CI mode without --yes-i-mean-it, the prompt is "delete all".
    runner = CliRunner()
    result = runner.invoke(build_app(), ["auth", "revoke", "--all"], input="no\n")
    assert result.exit_code != 0
