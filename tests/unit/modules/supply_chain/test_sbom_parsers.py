"""Per-lockfile parser tests (Phase 33.01).

Every parser must:

- Extract every pinned ``name@version`` it can recognise.
- Skip non-pin lines silently (range specs, git URLs, comments).
- Emit a valid ``pkg:`` purl per :func:`modules.supply_chain.lockfiles._purl_for`.
- Be byte-stable across re-runs (no clock / random data).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.supply_chain.lockfiles import (
    DetectedLockfile,
    detect_lockfiles,
    parse_lockfile,
    parse_package_lock_json,
    parse_pipfile_lock,
    parse_pnpm_lock_yaml,
    parse_poetry_lock,
    parse_requirements_txt,
    parse_uv_lock,
    parse_yarn_lock,
)
from modules.supply_chain.models import SbomComponent


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_detect_lockfiles_finds_each_known_shape(tmp_path: Path) -> None:
    for name in (
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "requirements.txt",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    ):
        _write(tmp_path / name, "")
    detected = detect_lockfiles(tmp_path)
    kinds = [d.kind for d in detected]
    assert kinds == [
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "requirements.txt",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    ]


def test_detect_lockfiles_skips_missing(tmp_path: Path) -> None:
    _write(tmp_path / "uv.lock", "")
    detected = detect_lockfiles(tmp_path)
    assert [d.kind for d in detected] == ["uv.lock"]


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------


def test_parse_uv_lock(tmp_path: Path) -> None:
    body = (
        "version = 1\n"
        "\n"
        '[[package]]\nname = "fastapi"\nversion = "0.100.0"\n'
        '[[package]]\nname = "pydantic"\nversion = "2.5.1"\n'
    )
    path = _write(tmp_path / "uv.lock", body)
    components = parse_uv_lock(path)
    assert {(c.name, c.version) for c in components} == {
        ("fastapi", "0.100.0"),
        ("pydantic", "2.5.1"),
    }
    assert all(c.ecosystem == "PyPI" for c in components)
    assert all(c.purl.startswith("pkg:pypi/") for c in components)


def test_parse_poetry_lock_handles_v15_layout(tmp_path: Path) -> None:
    body = (
        '[[package]]\nname = "click"\nversion = "8.1.7"\n'
        '[[package]]\nname = "typer"\nversion = "0.15.1"\n'
    )
    path = _write(tmp_path / "poetry.lock", body)
    components = parse_poetry_lock(path)
    assert ("click", "8.1.7") in {(c.name, c.version) for c in components}
    assert ("typer", "0.15.1") in {(c.name, c.version) for c in components}


def test_parse_pipfile_lock_marks_default_as_direct(tmp_path: Path) -> None:
    payload = {
        "default": {
            "requests": {"version": "==2.31.0"},
        },
        "develop": {
            "pytest": {"version": "==7.4.0"},
        },
    }
    path = _write(tmp_path / "Pipfile.lock", json.dumps(payload))
    components = parse_pipfile_lock(path)
    by_name = {c.name: c for c in components}
    assert by_name["requests"].direct is True
    assert by_name["requests"].version == "2.31.0"
    assert by_name["pytest"].direct is False


def test_parse_requirements_txt_skips_non_pins(tmp_path: Path) -> None:
    body = "# comment\nrequests==2.31.0\nflask>=2.0\nsentinelqa @ git+https://example.com\n"
    path = _write(tmp_path / "requirements.txt", body)
    components = parse_requirements_txt(path)
    assert [c.name for c in components] == ["requests"]


def test_parse_requirements_txt_supports_extras_and_markers(tmp_path: Path) -> None:
    body = "pydantic[email]==2.5.1; python_version >= '3.11'\n"
    path = _write(tmp_path / "requirements.txt", body)
    components = parse_requirements_txt(path)
    assert components and components[0].name == "pydantic"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def test_parse_package_lock_v3(tmp_path: Path) -> None:
    payload = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "root"},
            "node_modules/lodash": {"version": "4.17.21", "license": "MIT"},
            "node_modules/@scope/pkg": {"version": "1.0.0"},
        },
    }
    path = _write(tmp_path / "package-lock.json", json.dumps(payload))
    components = parse_package_lock_json(path)
    by_name = {c.name: c for c in components}
    assert by_name["lodash"].version == "4.17.21"
    assert by_name["lodash"].licenses == ("MIT",)
    assert by_name["@scope/pkg"].purl.startswith("pkg:npm/")


def test_parse_package_lock_v1_legacy(tmp_path: Path) -> None:
    payload = {
        "lockfileVersion": 1,
        "dependencies": {
            "lodash": {"version": "4.17.20"},
        },
    }
    path = _write(tmp_path / "package-lock.json", json.dumps(payload))
    components = parse_package_lock_json(path)
    assert components == (
        SbomComponent(
            name="lodash",
            version="4.17.20",
            ecosystem="npm",
            purl="pkg:npm/lodash@4.17.20",
            direct=True,
        ),
    )


def test_parse_pnpm_lock_v9_keys(tmp_path: Path) -> None:
    body = (
        "lockfileVersion: '9.0'\n"
        "packages:\n"
        "  /lodash@4.17.21:\n"
        "    resolution: {integrity: sha512-XYZ}\n"
        "  '/@scope/pkg@1.0.0':\n"
        "    resolution: {integrity: sha512-XYZ}\n"
        "  '/peer@1.0.0(react@18.0.0)':\n"
        "    resolution: {integrity: sha512-XYZ}\n"
    )
    path = _write(tmp_path / "pnpm-lock.yaml", body)
    components = parse_pnpm_lock_yaml(path)
    names = {c.name for c in components}
    assert "lodash" in names
    assert "@scope/pkg" in names
    assert "peer" in names


def test_parse_yarn_lock_classic(tmp_path: Path) -> None:
    body = (
        '"lodash@^4.17.0", "lodash@^4.17.21":\n'
        '  version "4.17.21"\n'
        "\n"
        '"@scope/pkg@^1.0.0":\n'
        '  version "1.0.0"\n'
    )
    path = _write(tmp_path / "yarn.lock", body)
    components = parse_yarn_lock(path)
    names = {c.name: c.version for c in components}
    assert names["lodash"] == "4.17.21"
    assert names["@scope/pkg"] == "1.0.0"


def test_parse_yarn_lock_skips_metadata(tmp_path: Path) -> None:
    body = "__metadata:\n" "  version: 6\n" "\n" '"lodash@^4.0.0":\n' '  version "4.17.21"\n'
    path = _write(tmp_path / "yarn.lock", body)
    components = parse_yarn_lock(path)
    assert [c.name for c in components] == ["lodash"]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_parse_lockfile_dispatches_on_kind(tmp_path: Path) -> None:
    path = _write(tmp_path / "requirements.txt", "requests==2.31.0\n")
    detected = DetectedLockfile(path=path, kind="requirements.txt", ecosystem="PyPI")
    components = parse_lockfile(detected)
    assert components and components[0].name == "requests"


def test_parse_uv_lock_rejects_malformed(tmp_path: Path) -> None:
    import tomllib

    path = _write(tmp_path / "uv.lock", "not valid toml [[[")
    with pytest.raises(tomllib.TOMLDecodeError):
        parse_uv_lock(path)
