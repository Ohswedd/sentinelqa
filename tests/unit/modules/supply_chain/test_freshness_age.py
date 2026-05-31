"""Lockfile age tests (Phase 33.03)."""

from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime
from pathlib import Path

from modules.supply_chain.freshness import (
    DEFAULT_THRESHOLD_DAYS,
    compute_lockfile_age_days,
    evaluate_freshness,
)


def _write(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _backdate(path: Path, days: int) -> None:
    """Set mtime ``days`` days into the past so the freshness check
    perceives the file as that old, regardless of when the test runs."""

    age_seconds = days * 86_400
    target = time.time() - age_seconds
    os.utime(path, (target, target))


def test_compute_lockfile_age_days_uses_mtime(tmp_path: Path) -> None:
    path = _write(tmp_path / "uv.lock")
    _backdate(path, 365)
    today = date.today()
    age = compute_lockfile_age_days(path, tmp_path, today=today)
    assert 364 <= age <= 366


def test_compute_lockfile_age_days_clamps_to_zero(tmp_path: Path) -> None:
    path = _write(tmp_path / "uv.lock")
    # mtime is "now"; backdated 0 days; check today.
    today = date.today()
    age = compute_lockfile_age_days(path, tmp_path, today=today)
    assert age == 0


def test_compute_lockfile_age_days_handles_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "absent.lock"
    age = compute_lockfile_age_days(path, tmp_path, today=date.today())
    assert age == 0


def test_default_threshold_constant() -> None:
    assert DEFAULT_THRESHOLD_DAYS == 180


def test_evaluate_freshness_flags_stale_lockfile(tmp_path: Path) -> None:
    path = _write(tmp_path / "package-lock.json", '{"lockfileVersion": 3, "packages": {}}')
    _backdate(path, 365)
    report = evaluate_freshness(
        project_root=tmp_path,
        threshold_days=90,
        now=datetime.now(UTC),
    )
    assert any(lf.stale for lf in report.lockfiles)
    assert all(lf.threshold_days == 90 for lf in report.lockfiles)


def test_evaluate_freshness_no_lockfiles_is_skipped(tmp_path: Path) -> None:
    report = evaluate_freshness(project_root=tmp_path)
    assert report.skipped is True
    assert report.lockfiles == ()


def test_evaluate_freshness_respects_custom_threshold(tmp_path: Path) -> None:
    path = _write(tmp_path / "uv.lock")
    _backdate(path, 200)
    report = evaluate_freshness(
        project_root=tmp_path,
        threshold_days=300,
        now=datetime.now(UTC),
    )
    assert report.lockfiles[0].stale is False
