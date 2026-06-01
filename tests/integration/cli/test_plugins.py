"""CLI integration tests for ``sentinel plugins``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.plugins import LoadedPlugin, PluginRegistry, load_manifest_dict
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from sentinel_cli.commands import plugins_cmd

VALID_MANIFEST = {
    "name": "tiny-scanner",
    "version": "0.1.0",
    "kind": "scanner",
    "capabilities": ["audit"],
    "permissions": ["fs.read"],
    "requires_protocol": ">=1.0,<2.0",
    "description": "Reference scanner for tests.",
}


def _populated_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.add(
        LoadedPlugin(
            manifest=load_manifest_dict(VALID_MANIFEST),
            instance=object(),
            entry_point_name="tiny-scanner",
            distribution="sentinelqa-scanner-example",
            distribution_version="0.1.0",
        )
    )
    return registry


def _registry_with_errors() -> PluginRegistry:
    registry = PluginRegistry()
    registry.record_error(plugin="broken", stage="validate", detail="forbidden capability")
    return registry


# ---------------------------------------------------------------------------
# Help & no-args
# ---------------------------------------------------------------------------


def test_plugins_help_lists_subcommands() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "--help"])
    assert result.exit_code == 0
    for cmd in ("list", "info", "validate"):
        assert cmd in result.stdout


def test_plugins_no_args_shows_help() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins"])
    # no_args_is_help => Typer exits non-zero with the help text.
    assert "list" in result.stdout


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_plugins_list_empty_environment() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "list"])
    assert result.exit_code == 0
    assert "No SentinelQA plugins installed." in result.stdout


def test_plugins_list_json_mode_returns_envelope() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["--json", "plugins", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["host_protocol_version"]
    assert payload["plugins"] == []
    assert payload["errors"] == []


# ---------------------------------------------------------------------------
# info — error path is reachable without installing a plugin.
# ---------------------------------------------------------------------------


def test_plugins_info_missing_returns_exit_2() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "info", "nope"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_plugins_validate_accepts_valid_manifest(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
    result = runner.invoke(build_app(), ["plugins", "validate", str(manifest_path)])
    assert result.exit_code == 0
    assert "OK: tiny-scanner" in result.stdout


def test_plugins_validate_rejects_bad_manifest(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    bad = dict(VALID_MANIFEST)
    bad["name"] = "Bad Name"  # uppercase + space → invalid
    bad_path = tmp_path / "manifest.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = runner.invoke(build_app(), ["plugins", "validate", str(bad_path)])
    assert result.exit_code == 2


def test_plugins_validate_rejects_forbidden_capability(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    bad = dict(VALID_MANIFEST)
    bad["capabilities"] = ["audit", "bot_detection_bypass"]
    bad_path = tmp_path / "manifest.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = runner.invoke(build_app(), ["plugins", "validate", str(bad_path)])
    assert result.exit_code == 2


def test_plugins_validate_handles_missing_file(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        ["plugins", "validate", str(tmp_path / "does-not-exist.json")],
    )
    assert result.exit_code == 2


def test_plugins_validate_json_mode(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
    result = runner.invoke(
        build_app(),
        ["--json", "plugins", "validate", str(manifest_path)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True
    assert payload["manifest"]["name"] == "tiny-scanner"


def test_plugins_list_renders_human_table_when_populated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins_cmd, "discover", lambda: _populated_registry())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "list"])
    assert result.exit_code == 0
    assert "Host protocol version" in result.stdout
    assert "tiny-scanner" in result.stdout
    assert "scanner" in result.stdout


def test_plugins_list_json_returns_populated_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins_cmd, "discover", lambda: _populated_registry())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["--json", "plugins", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["plugins"]
    plug = payload["plugins"][0]
    assert plug["name"] == "tiny-scanner"
    assert plug["entry_point"] == "tiny-scanner"
    assert plug["distribution"] == "sentinelqa-scanner-example"


def test_plugins_list_shows_errors_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins_cmd, "discover", lambda: _registry_with_errors())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "list", "--show-errors"])
    assert result.exit_code == 0
    assert "Discovery errors:" in result.stdout
    assert "broken" in result.stdout


def test_plugins_info_renders_human_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins_cmd, "discover", lambda: _populated_registry())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["plugins", "info", "tiny-scanner"])
    assert result.exit_code == 0
    assert "name:" in result.stdout
    assert "version:" in result.stdout
    assert "tiny-scanner" in result.stdout
    assert "description:" in result.stdout


def test_plugins_info_json_returns_manifest_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plugins_cmd, "discover", lambda: _populated_registry())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(build_app(), ["--json", "plugins", "info", "tiny-scanner"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["manifest"]["name"] == "tiny-scanner"
    assert payload["distribution"] == "sentinelqa-scanner-example"
    assert payload["host_protocol_version"]


def test_plugins_validate_json_error_envelope(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    bad = dict(VALID_MANIFEST)
    bad["kind"] = "weirdo"
    bad_path = tmp_path / "manifest.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = runner.invoke(build_app(), ["--json", "plugins", "validate", str(bad_path)])
    assert result.exit_code == 2
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    assert payload["code"].startswith("E-PLG-")
