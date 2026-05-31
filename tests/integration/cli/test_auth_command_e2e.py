"""End-to-end ``sentinel auth`` round-trip (login → list → export → revoke)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import sentinel_cli.commands.auth_cmd as auth_cmd
from sentinel_cli.app import build_app


class _StubLauncher:
    """Returns a fixed (storage_state, landed_url) pair — no browser."""

    def __init__(self, storage_state: dict[str, Any], landed_url: str) -> None:
        self._storage_state = storage_state
        self._landed_url = landed_url

    def capture(
        self,
        *,
        login_url: str,
        browser: str,
        confirm: Callable[[str], str],
    ) -> tuple[dict[str, Any], str]:
        confirm("press enter > ")
        return self._storage_state, self._landed_url


@pytest.fixture
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the vault root, salt path, passphrase, and HOME."""

    vault_root = tmp_path / "vault"
    monkeypatch.setenv("SENTINEL_VAULT_ROOT", str(vault_root))
    monkeypatch.setenv("SENTINEL_VAULT_SALT_PATH", str(tmp_path / ".salt"))
    monkeypatch.setenv("SENTINEL_VAULT_PASSPHRASE", "test-only-passphrase-1234567890ab")
    monkeypatch.setenv("HOME", str(tmp_path))
    return vault_root


def _install_stub_launcher(
    monkeypatch: pytest.MonkeyPatch,
    storage_state: dict[str, Any],
    landed_url: str = "https://github.com/",
) -> None:
    monkeypatch.setattr(
        auth_cmd,
        "_resolve_launcher",
        lambda: _StubLauncher(storage_state, landed_url),
    )


def _stub_storage() -> dict[str, Any]:
    return {
        "cookies": [
            {
                "name": "user_session",
                "value": "long-real-session-value-abc123def456",
                "domain": "github.com",
            }
        ],
        "origins": [
            {
                "origin": "https://github.com",
                "localStorage": [{"name": "k", "value": "v"}],
            }
        ],
    }


def test_login_then_list_then_revoke_round_trip(
    auth_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()

    # login
    result = runner.invoke(
        build_app(),
        [
            "auth",
            "login",
            "github-myorg",
            "--url",
            "https://github.com/login",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Captured session for github.com" in result.stdout

    # list (human + JSON)
    result_h = runner.invoke(build_app(), ["auth", "list"])
    assert result_h.exit_code == 0
    assert "github.com" in result_h.stdout
    assert "github-myorg" in result_h.stdout
    assert "ok" in result_h.stdout

    result_j = runner.invoke(build_app(), ["--json", "auth", "list"])
    assert result_j.exit_code == 0
    payload = json.loads(result_j.stdout.strip().splitlines()[-1])
    assert payload["count"] == 1
    assert payload["entries"][0]["name"] == "github-myorg"
    assert payload["entries"][0]["host"] == "github.com"
    # The cookie value never appears in the list output.
    assert "long-real-session-value-abc123def456" not in result_h.stdout
    assert "long-real-session-value-abc123def456" not in result_j.stdout

    # revoke
    result_r = runner.invoke(
        build_app(),
        ["auth", "revoke", "github-myorg", "--host", "github.com"],
    )
    assert result_r.exit_code == 0
    assert "Removed vault entry" in result_r.stdout

    # list again — empty.
    result_h2 = runner.invoke(build_app(), ["auth", "list"])
    assert "No vault entries" in result_h2.stdout


def test_login_refuses_overwrite_without_force(
    auth_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()

    first = runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    assert first.exit_code == 0

    second = runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    # `VaultError` propagates as a generic runtime failure (exit != 0).
    assert second.exit_code != 0


def test_login_force_overwrites(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()

    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    overwrite = runner.invoke(
        build_app(),
        [
            "auth",
            "login",
            "github-myorg",
            "--url",
            "https://github.com/login",
            "--force",
        ],
    )
    assert overwrite.exit_code == 0


def test_login_with_profile_succeeds(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Profile + a successful capture exercises the banner-with-profile path.
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "auth",
            "login",
            "github-myorg",
            "--url",
            "https://github.com/login",
            "--profile",
            "github-oauth",
        ],
    )
    assert result.exit_code == 0


def test_login_json_mode_emits_json(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    # mix_stderr=False so the banner-on-stderr doesn't pollute stdout.
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "auth",
            "login",
            "github-myorg",
            "--url",
            "https://github.com/login",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["host"] == "github.com"
    assert payload["name"] == "github-myorg"


def test_revoke_unknown_entry_returns_zero(auth_env: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        ["auth", "revoke", "nope", "--host", "github.com"],
    )
    assert result.exit_code == 0
    assert "No vault entry" in result.stdout


def test_revoke_all_with_yes_flag_drops_every_entry(
    auth_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    result = runner.invoke(
        build_app(),
        ["auth", "revoke", "--all", "--yes-i-mean-it"],
    )
    assert result.exit_code == 0
    list_after = runner.invoke(build_app(), ["auth", "list"])
    assert "No vault entries" in list_after.stdout


def test_revoke_all_typed_confirmation_drops_entries(
    auth_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    confirmed = runner.invoke(
        build_app(),
        ["auth", "revoke", "--all"],
        input="delete all\n",
    )
    assert confirmed.exit_code == 0


def test_export_round_trip(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    out_path = auth_env.parent / "exported.json"
    result = runner.invoke(
        build_app(),
        [
            "auth",
            "export",
            "github-myorg",
            "--host",
            "github.com",
            "--out",
            str(out_path),
            "--i-acknowledge",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "cookies" in payload


def test_login_rejects_url_without_host(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        ["auth", "login", "x", "--url", "not-a-url"],
    )
    assert result.exit_code != 0


def test_list_filtered_by_host(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner()
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )

    # An entry filed under another host shouldn't appear when the filter
    # excludes it; we don't have another host wired, so just exercise the
    # filter with the real host and an unrelated host.
    result_match = runner.invoke(build_app(), ["auth", "list", "--host", "github.com"])
    assert "github-myorg" in result_match.stdout
    result_miss = runner.invoke(build_app(), ["auth", "list", "--host", "other.com"])
    assert "No vault entries" in result_miss.stdout


def test_revoke_json_mode_emits_json(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner(mix_stderr=False)
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "auth",
            "revoke",
            "github-myorg",
            "--host",
            "github.com",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["removed"] is True


def test_revoke_all_json_mode_emits_json(auth_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner(mix_stderr=False)
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    result = runner.invoke(
        build_app(),
        ["--json", "auth", "revoke", "--all", "--yes-i-mean-it"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["scope"] == "all"


def test_export_json_mode_emits_json(
    auth_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_stub_launcher(monkeypatch, _stub_storage())
    runner = CliRunner(mix_stderr=False)
    runner.invoke(
        build_app(),
        ["auth", "login", "github-myorg", "--url", "https://github.com/login"],
    )
    out_path = tmp_path / "out.json"
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "auth",
            "export",
            "github-myorg",
            "--host",
            "github.com",
            "--out",
            str(out_path),
            "--i-acknowledge",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["host"] == "github.com"


def test_revoke_all_in_ci_mode_requires_yes_flag(auth_env: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        ["--ci", "auth", "revoke", "--all"],
    )
    assert result.exit_code != 0
