"""Lockfile parser defensive-shape coverage (Phase 33.01)."""

from __future__ import annotations

import json
from pathlib import Path

from modules.supply_chain.lockfiles import (
    parse_package_lock_json,
    parse_pipfile_lock,
    parse_pnpm_lock_yaml,
    parse_poetry_lock,
    parse_uv_lock,
    parse_yarn_lock,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_uv_lock_skips_packages_with_no_name(tmp_path: Path) -> None:
    body = '[[package]]\nversion = "1.0.0"\n[[package]]\nname = "ok"\nversion = "2.0.0"\n'
    path = _write(tmp_path / "uv.lock", body)
    assert [c.name for c in parse_uv_lock(path)] == ["ok"]


def test_parse_uv_lock_returns_empty_when_package_is_not_list(tmp_path: Path) -> None:
    body = 'package = "not a list"\n'
    path = _write(tmp_path / "uv.lock", body)
    assert parse_uv_lock(path) == ()


def test_parse_poetry_lock_returns_empty_when_package_is_not_list(tmp_path: Path) -> None:
    body = 'package = "scalar"\n'
    path = _write(tmp_path / "poetry.lock", body)
    assert parse_poetry_lock(path) == ()


def test_parse_poetry_lock_skips_dict_without_name(tmp_path: Path) -> None:
    body = '[[package]]\nversion = "1.0.0"\n'
    path = _write(tmp_path / "poetry.lock", body)
    assert parse_poetry_lock(path) == ()


def test_parse_pipfile_lock_handles_section_that_is_not_dict(tmp_path: Path) -> None:
    body = json.dumps({"default": "not a dict", "develop": {}})
    path = _write(tmp_path / "Pipfile.lock", body)
    assert parse_pipfile_lock(path) == ()


def test_parse_pipfile_lock_skips_entries_with_blank_version(tmp_path: Path) -> None:
    body = json.dumps(
        {
            "default": {"empty": {"version": "=="}, "ok": {"version": "==1.2.3"}},
        }
    )
    path = _write(tmp_path / "Pipfile.lock", body)
    assert [c.name for c in parse_pipfile_lock(path)] == ["ok"]


def test_parse_package_lock_v3_skips_non_dict_entries(tmp_path: Path) -> None:
    body = json.dumps(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "root"},
                "node_modules/x": "not a dict",
                "node_modules/y": {"version": "2.0.0"},
            },
        }
    )
    path = _write(tmp_path / "package-lock.json", body)
    components = parse_package_lock_json(path)
    assert [c.name for c in components] == ["y"]


def test_parse_pnpm_returns_empty_when_top_level_not_dict(tmp_path: Path) -> None:
    body = "- 1\n- 2\n"
    path = _write(tmp_path / "pnpm-lock.yaml", body)
    assert parse_pnpm_lock_yaml(path) == ()


def test_parse_pnpm_returns_empty_when_packages_block_absent(tmp_path: Path) -> None:
    body = "lockfileVersion: '9.0'\n"
    path = _write(tmp_path / "pnpm-lock.yaml", body)
    assert parse_pnpm_lock_yaml(path) == ()


def test_parse_yarn_lock_handles_blank_input(tmp_path: Path) -> None:
    path = _write(tmp_path / "yarn.lock", "\n\n\n")
    assert parse_yarn_lock(path) == ()
