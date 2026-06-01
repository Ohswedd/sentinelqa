"""Targeted coverage tests for the supply-chain helper / fallback paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from modules.supply_chain.freshness import (
    _last_git_touch,
    _read_json,
    _read_toml,
    _read_yaml,
    detect_npm_drift,
    detect_pnpm_drift,
    detect_python_drift,
    evaluate_freshness,
)
from modules.supply_chain.lockfiles import (
    _name_from_yarn_spec,
    _split_pnpm_key,
    parse_package_lock_json,
    parse_pipfile_lock,
    parse_pnpm_lock_yaml,
    parse_requirements_txt,
    parse_yarn_lock,
)
from modules.supply_chain.postinstall import (
    scan_npm_packages,
    scan_python_packages,
    scan_python_setup_py,
)

# ---------------------------------------------------------------------------
# freshness helpers
# ---------------------------------------------------------------------------


def test_last_git_touch_outside_repo(tmp_path: Path) -> None:
    assert _last_git_touch(tmp_path / "anything", tmp_path) is None


def test_read_helpers_handle_invalid_payloads(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    assert _read_json(bad_json) == {}

    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(":\n - [", encoding="utf-8")
    assert _read_yaml(bad_yaml) == {}

    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("[invalid", encoding="utf-8")
    assert _read_toml(bad_toml) == {}


def test_read_json_non_dict_returns_empty(tmp_path: Path) -> None:
    list_json = tmp_path / "list.json"
    list_json.write_text("[1,2,3]", encoding="utf-8")
    assert _read_json(list_json) == {}


def test_detect_npm_drift_returns_empty_when_no_manifest(tmp_path: Path) -> None:
    # Missing both files
    assert detect_npm_drift(tmp_path) == ()
    # Manifest with empty deps
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {}}), encoding="utf-8")
    (tmp_path / "package-lock.json").write_text(
        json.dumps({"lockfileVersion": 3, "packages": {}}), encoding="utf-8"
    )
    assert detect_npm_drift(tmp_path) == ()


def test_detect_pnpm_drift_when_pyproject_empty(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("packages: {}\n", encoding="utf-8")
    assert detect_pnpm_drift(tmp_path) == ()


def test_detect_python_drift_when_pyproject_empty(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    assert detect_python_drift(tmp_path, "uv.lock") == ()


def test_evaluate_freshness_unknown_lockfile_kind_does_not_check_drift(tmp_path: Path) -> None:
    (tmp_path / "Pipfile.lock").write_text(json.dumps({"default": {}}), encoding="utf-8")
    report = evaluate_freshness(project_root=tmp_path, now=datetime.now(UTC))
    assert report.lockfiles
    assert report.lockfiles[0].manifest_drift == ()


# ---------------------------------------------------------------------------
# lockfiles helpers
# ---------------------------------------------------------------------------


def test_parse_yarn_lock_skips_metadata_header(tmp_path: Path) -> None:
    yarn = tmp_path / "yarn.lock"
    yarn.write_text(
        "# yarn lockfile v1\n\n__metadata:\n  version: 6\n\n",
        encoding="utf-8",
    )
    assert parse_yarn_lock(yarn) == ()


def test_parse_yarn_lock_handles_broken_entry(tmp_path: Path) -> None:
    yarn = tmp_path / "yarn.lock"
    yarn.write_text("not-a-spec\n  bogus content\n", encoding="utf-8")
    assert parse_yarn_lock(yarn) == ()


def test_parse_pipfile_lock_skips_non_string_versions(tmp_path: Path) -> None:
    pipfile = tmp_path / "Pipfile.lock"
    pipfile.write_text(
        json.dumps(
            {
                "default": {
                    "good": {"version": "==1.0.0"},
                    "bad": {"version": None},
                    "weird": "not even a dict",
                }
            }
        ),
        encoding="utf-8",
    )
    components = parse_pipfile_lock(pipfile)
    assert [c.name for c in components] == ["good"]


def test_parse_requirements_skips_options_and_blanks(tmp_path: Path) -> None:
    body = "\n# pinned deps\nrequests==2.31.0\n-r other.txt\n\n--index-url=https://example.com\n"
    req = tmp_path / "requirements.txt"
    req.write_text(body, encoding="utf-8")
    components = parse_requirements_txt(req)
    assert [c.name for c in components] == ["requests"]


def test_parse_package_lock_returns_empty_for_root_only(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"lockfileVersion": 3, "packages": {"": {}}}), encoding="utf-8")
    assert parse_package_lock_json(lock) == ()


def test_parse_pnpm_handles_unknown_key_shape(tmp_path: Path) -> None:
    lock = tmp_path / "pnpm-lock.yaml"
    lock.write_text(
        "packages:\n  not-a-valid-key:\n    resolution: {integrity: sha512-XYZ}\n",
        encoding="utf-8",
    )
    # Unknown key shape → no components.
    assert parse_pnpm_lock_yaml(lock) == ()


def test_split_pnpm_key_uses_entry_metadata() -> None:
    name, version = _split_pnpm_key("/anything", {"name": "explicit", "version": "9.9.9"})
    assert (name, version) == ("explicit", "9.9.9")


def test_name_from_yarn_spec_supports_scopes() -> None:
    assert _name_from_yarn_spec("@scope/pkg@^1.0.0") == "@scope/pkg"
    assert _name_from_yarn_spec("plain@^1.0.0") == "plain"
    assert _name_from_yarn_spec("@scope/") is None


# ---------------------------------------------------------------------------
# postinstall helpers
# ---------------------------------------------------------------------------


def test_scan_npm_packages_returns_empty_when_no_node_modules(tmp_path: Path) -> None:
    assert scan_npm_packages(tmp_path / "node_modules") == ()


def test_scan_python_packages_handles_missing_dirs(tmp_path: Path) -> None:
    # No venv /.venv /.tox -> nothing to scan.
    assert scan_python_packages(tmp_path) == ()


def test_scan_python_setup_py_returns_empty_for_unreadable_path(tmp_path: Path) -> None:
    assert scan_python_setup_py(tmp_path / "missing.py") == ()


def test_scan_python_setup_py_flags_socket_import(tmp_path: Path) -> None:
    setup = tmp_path / "sock" / "setup.py"
    setup.parent.mkdir()
    setup.write_text("import socket\nsocket.gethostbyname('x')\n", encoding="utf-8")
    issues = scan_python_setup_py(setup)
    assert any(i.pattern == "import:socket" for i in issues)
