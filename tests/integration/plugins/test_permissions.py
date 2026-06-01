"""— capability + permission declarations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.plugins import (
    Manifest,
    PluginContextImpl,
    PluginPermissionError,
    build_plugin_context,
    load_manifest_dict,
    load_manifest_file,
)
from engine.plugins.errors import (
    PluginCapabilityForbiddenError,
    PluginManifestError,
)

# ---------------------------------------------------------------------------
# Manifest schema validation
# ---------------------------------------------------------------------------


def test_manifest_round_trips_minimal_valid_payload() -> None:
    manifest = load_manifest_dict(
        {
            "name": "tiny",
            "version": "0.1.0",
            "kind": "scanner",
            "capabilities": ["audit"],
            "permissions": ["fs.read"],
            "requires_protocol": ">=1.0,<2.0",
        }
    )

    assert isinstance(manifest, Manifest)
    assert manifest.capabilities == ("audit",)
    assert manifest.permissions == ("fs.read",)


def test_manifest_rejects_extra_keys() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "requires_protocol": ">=1.0",
                "extra_key": "boom",
            }
        )


def test_manifest_rejects_bad_name() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "Bad Name",
                "version": "0.1.0",
                "kind": "scanner",
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_bad_version() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "v1",
                "kind": "scanner",
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_unknown_kind() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "weirdo",
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_unscoped_fs_write() -> None:
    # fs.write must be scoped to ``.sentinel/runs`` — anything else is
    # outside the plugin contract.
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "permissions": ["fs.write:/etc"],
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_bad_permission_grammar() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "permissions": ["NETWORK.OUTBOUND"],
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_duplicate_permissions() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "permissions": ["fs.read", "fs.read"],
                "requires_protocol": ">=1.0",
            }
        )


def test_manifest_rejects_empty_requires_protocol() -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "requires_protocol": "   ",
            }
        )


def test_manifest_accepts_scoped_read_and_env_permissions() -> None:
    manifest = load_manifest_dict(
        {
            "name": "tiny",
            "version": "0.1.0",
            "kind": "scanner",
            "permissions": ["fs.read:/srv", "env.read:DATABASE_URL"],
            "requires_protocol": ">=1.0",
        }
    )

    assert "env.read:DATABASE_URL" in manifest.permissions


def test_manifest_assert_no_forbidden_capabilities_raises() -> None:
    manifest = load_manifest_dict(
        {
            "name": "tiny",
            "version": "0.1.0",
            "kind": "scanner",
            "capabilities": ["bot_detection_bypass"],
            "requires_protocol": ">=1.0",
        }
    )
    with pytest.raises(PluginCapabilityForbiddenError):
        manifest.assert_no_forbidden_capabilities()


def test_load_manifest_file_json(tmp_path: Path) -> None:
    payload = {
        "name": "tiny",
        "version": "0.1.0",
        "kind": "scanner",
        "requires_protocol": ">=1.0",
    }
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_manifest_file(target)

    assert manifest.name == "tiny"


def test_load_manifest_file_toml(tmp_path: Path) -> None:
    target = tmp_path / "manifest.toml"
    target.write_text(
        "\n".join(
            [
                'name = "tiny"',
                'version = "0.1.0"',
                'kind = "scanner"',
                'requires_protocol = ">=1.0"',
            ]
        ),
        encoding="utf-8",
    )

    manifest = load_manifest_file(target)

    assert manifest.kind == "scanner"


def test_load_manifest_file_rejects_unknown_suffix(tmp_path: Path) -> None:
    target = tmp_path / "manifest.yaml"
    target.write_text("name: tiny", encoding="utf-8")
    with pytest.raises(PluginManifestError):
        load_manifest_file(target)


def test_load_manifest_file_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_file(tmp_path / "missing.json")


def test_load_manifest_file_rejects_malformed_json(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(PluginManifestError):
        load_manifest_file(target)


def test_load_manifest_file_rejects_non_object_top_level(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    target.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(PluginManifestError):
        load_manifest_file(target)


# ---------------------------------------------------------------------------
# Runtime permission enforcement
# ---------------------------------------------------------------------------


def _ctx(tmp_path: Path, **kwargs) -> PluginContextImpl:
    return build_plugin_context(
        plugin_name=kwargs.pop("plugin_name", "tiny"),
        run_id=kwargs.pop("run_id", "RUN-test"),
        target_url=kwargs.pop("target_url", "http://localhost"),
        run_dir=kwargs.pop("run_dir", tmp_path),
        config_snapshot=kwargs.pop("config_snapshot", {}),
        granted_permissions=kwargs.pop("granted_permissions", frozenset()),
    )


def test_has_permission_matches_declared(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, granted_permissions=frozenset({"fs.read"}))
    assert ctx.has_permission("fs.read")
    assert not ctx.has_permission("fs.write:.sentinel/runs")


def test_has_permission_matches_scoped_to_unscoped(tmp_path: Path) -> None:
    # A plugin that declared fs.read:/srv satisfies a 'fs.read' check.
    ctx = _ctx(tmp_path, granted_permissions=frozenset({"fs.read:/srv"}))
    assert ctx.has_permission("fs.read")


def test_require_raises_when_missing(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(PluginPermissionError):
        ctx.require("network.outbound")


def test_artifact_path_requires_write_permission(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(PluginPermissionError):
        ctx.artifact_path("out.json")


def test_artifact_path_confines_under_run_dir(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        granted_permissions=frozenset({"fs.write:.sentinel/runs"}),
    )
    p = ctx.artifact_path("out.json")
    assert p.parent.parent == tmp_path / "plugins"


def test_artifact_path_rejects_traversal(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        granted_permissions=frozenset({"fs.write:.sentinel/runs"}),
    )
    with pytest.raises(PluginPermissionError):
        ctx.artifact_path("../escape.txt")


def test_artifact_path_rejects_absolute(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        granted_permissions=frozenset({"fs.write:.sentinel/runs"}),
    )
    with pytest.raises(PluginPermissionError):
        ctx.artifact_path("/etc/passwd")


def test_env_requires_scoped_permission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_VAR", "yes")
    monkeypatch.setenv("FORBIDDEN_VAR", "no")
    ctx = _ctx(
        tmp_path,
        granted_permissions=frozenset({"env.read:ALLOWED_VAR"}),
    )
    assert ctx.env("ALLOWED_VAR") == "yes"
    with pytest.raises(PluginPermissionError):
        ctx.env("FORBIDDEN_VAR")


def test_read_text_requires_fs_read(tmp_path: Path) -> None:
    file = tmp_path / "data.txt"
    file.write_text("hello", encoding="utf-8")
    ctx = _ctx(tmp_path)
    with pytest.raises(PluginPermissionError):
        ctx.read_text(file)

    ctx_ok = _ctx(tmp_path, granted_permissions=frozenset({"fs.read"}))
    assert ctx_ok.read_text(file) == "hello"


def test_permission_error_carries_redacted_context(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, plugin_name="tiny")
    try:
        ctx.require("network.outbound")
    except PluginPermissionError as exc:
        msg = exc.to_agent_message()
        assert msg["code"] == "E-PLG-002"
        assert msg["context"]["plugin"] == "tiny"
        assert msg["context"]["permission"] == "network.outbound"


def test_plugin_artifact_directory_runs_outside_runs_root(tmp_path: Path) -> None:
    # The plugin context confines writes under <run_dir>/plugins/<name>/;
    # passing in an arbitrary tmp_path as run_dir is exercising the
    # "writes under our supplied dir" guarantee, not the runs-root rule.
    ctx = _ctx(
        tmp_path,
        granted_permissions=frozenset({"fs.write:.sentinel/runs"}),
    )
    out = ctx.artifact_path("nested/file.txt")
    out.write_text("hi", encoding="utf-8")
    assert (tmp_path / "plugins" / "tiny" / "nested" / "file.txt").read_text() == "hi"
