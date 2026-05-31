"""Lockfile↔manifest drift tests (Phase 33.03)."""

from __future__ import annotations

import json
from pathlib import Path

from modules.supply_chain.freshness import (
    detect_npm_drift,
    detect_pnpm_drift,
    detect_python_drift,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_npm_drift_finds_missing_dep(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"dependencies": {"lodash": "^4.0.0", "missing": "^1.0.0"}}),
    )
    _write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {"": {}, "node_modules/lodash": {"version": "4.17.21"}},
            }
        ),
    )
    drift = detect_npm_drift(tmp_path)
    assert any("missing" in entry for entry in drift)
    assert all("lodash" not in entry for entry in drift)


def test_npm_drift_empty_when_aligned(tmp_path: Path) -> None:
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"lodash": "^4.0.0"}}))
    _write(
        tmp_path / "package-lock.json",
        json.dumps(
            {
                "lockfileVersion": 3,
                "packages": {"": {}, "node_modules/lodash": {"version": "4.17.21"}},
            }
        ),
    )
    assert detect_npm_drift(tmp_path) == ()


def test_pnpm_drift_finds_missing_dep(tmp_path: Path) -> None:
    _write(
        tmp_path / "package.json",
        json.dumps({"dependencies": {"lodash": "^4.0.0", "missing": "^1.0.0"}}),
    )
    _write(
        tmp_path / "pnpm-lock.yaml",
        "packages:\n  /lodash@4.17.21: {}\n",
    )
    drift = detect_pnpm_drift(tmp_path)
    assert any("missing" in entry for entry in drift)


def test_python_drift_finds_missing_dep_in_uv_lock(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["pkg-a", "pkg-b"]\n',
    )
    _write(
        tmp_path / "uv.lock",
        '[[package]]\nname = "pkg-a"\nversion = "1.0.0"\n',
    )
    drift = detect_python_drift(tmp_path, "uv.lock")
    assert any("pkg-b" in entry for entry in drift)


def test_python_drift_skips_python_dep_in_poetry(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        '[tool.poetry.dependencies]\npython = "^3.11"\nrequests = "^2"\n',
    )
    _write(
        tmp_path / "poetry.lock",
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n',
    )
    drift = detect_python_drift(tmp_path, "poetry.lock")
    assert drift == ()


def test_drift_helpers_no_manifest_returns_empty(tmp_path: Path) -> None:
    assert detect_npm_drift(tmp_path) == ()
    assert detect_pnpm_drift(tmp_path) == ()
    assert detect_python_drift(tmp_path, "uv.lock") == ()
