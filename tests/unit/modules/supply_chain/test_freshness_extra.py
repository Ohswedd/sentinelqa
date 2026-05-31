"""Targeted freshness coverage — git fallback + PEP 508 normalisation."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from modules.supply_chain.freshness import (
    _last_git_touch,
    _normalize_pep508_name,
    _pyproject_direct_deps,
    _python_lock_names,
    compute_lockfile_age_days,
    detect_python_drift,
)


def test_last_git_touch_returns_none_when_git_not_on_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("no git")

    monkeypatch.setattr(subprocess, "run", boom)
    assert _last_git_touch(tmp_path / "x", tmp_path) is None


def test_last_git_touch_returns_none_on_subprocess_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.SubprocessError("boom")

    monkeypatch.setattr(subprocess, "run", boom)
    assert _last_git_touch(tmp_path / "x", tmp_path) is None


def test_last_git_touch_returns_none_on_empty_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def empty(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", empty)
    assert _last_git_touch(tmp_path / "x", tmp_path) is None


def test_last_git_touch_returns_none_on_invalid_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def garbage(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not-a-date", stderr="")

    monkeypatch.setattr(subprocess, "run", garbage)
    assert _last_git_touch(tmp_path / "x", tmp_path) is None


def test_last_git_touch_returns_date_on_valid_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def ok(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="2026-03-15", stderr="")

    monkeypatch.setattr(subprocess, "run", ok)
    assert _last_git_touch(tmp_path / "x", tmp_path) == date(2026, 3, 15)


def test_compute_lockfile_age_prefers_more_recent_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import time

    path = tmp_path / "uv.lock"
    path.write_text("", encoding="utf-8")
    # Backdate the lockfile to a year ago so the git date (2026-04-01) is
    # MORE recent than mtime — the helper should pick git's date.
    one_year_ago = time.time() - 365 * 86_400
    os.utime(path, (one_year_ago, one_year_ago))

    def fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="2026-04-01", stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    age = compute_lockfile_age_days(path, tmp_path, today=date(2026, 5, 31))
    assert age == 60


def test_compute_lockfile_age_handles_missing_path(tmp_path: Path) -> None:
    age = compute_lockfile_age_days(tmp_path / "nope.lock", tmp_path, today=date(2026, 5, 31))
    assert age == 0


def test_normalize_pep508_name_handles_each_delimiter() -> None:
    assert _normalize_pep508_name("requests==2.31.0") == "requests"
    assert _normalize_pep508_name("requests[security]") == "requests"
    assert _normalize_pep508_name("requests<3") == "requests"
    assert _normalize_pep508_name("requests>=2.31") == "requests"
    assert _normalize_pep508_name("requests; python_version >= '3.11'") == "requests"
    assert _normalize_pep508_name("") is None
    assert _normalize_pep508_name(123) is None


def test_pyproject_direct_deps_handles_optional_block() -> None:
    data = {
        "project": {
            "dependencies": ["requests"],
            "optional-dependencies": {
                "extra": ["pytest", 123],
                "wrong": "not a list",
            },
        }
    }
    deps = _pyproject_direct_deps(data)
    assert "requests" in deps
    assert "pytest" in deps


def test_pyproject_direct_deps_handles_poetry_skip_python_key() -> None:
    data = {
        "tool": {
            "poetry": {"dependencies": {"python": "^3.11", "Flask": "^2"}},
        }
    }
    deps = _pyproject_direct_deps(data)
    assert "flask" in deps
    assert "python" not in deps


def test_python_lock_names_returns_set_for_each_kind(tmp_path: Path) -> None:
    uv = tmp_path / "uv.lock"
    uv.write_text('[[package]]\nname = "Flask"\nversion = "3.0.0"\n', encoding="utf-8")
    assert _python_lock_names(uv, "uv.lock") == {"flask"}

    poetry = tmp_path / "poetry.lock"
    poetry.write_text('[[package]]\nname = "Click"\nversion = "8.0.0"\n', encoding="utf-8")
    assert _python_lock_names(poetry, "poetry.lock") == {"click"}

    # Other lockfile kinds fall through to an empty set.
    other = tmp_path / "requirements.txt"
    other.write_text("flask==1\n", encoding="utf-8")
    assert _python_lock_names(other, "requirements.txt") == set()


def test_detect_python_drift_finds_poetry_drift(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry.dependencies]\npython = '^3.11'\nrequests = '^2'\nflask = '^3'\n",
        encoding="utf-8",
    )
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n',
        encoding="utf-8",
    )
    drift = detect_python_drift(tmp_path, "poetry.lock")
    assert any("flask" in entry for entry in drift)
