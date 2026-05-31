# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""License-header audit in CI mode (Phase 35.03).

Runs `scripts.release.audit_license_headers` against the repo and
asserts the audit returns a clean report. Behaves the same way
`make audit-license-headers` would in CI — exit zero on a clean
tree, non-zero on drift or missing coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.release import audit_license_headers as auditor

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_repo_license_headers_clean() -> None:
    report = auditor.run_audit(REPO_ROOT)
    assert report.ok, auditor._format_report(report)


def test_audit_detects_foreign_spdx(tmp_path: Path) -> None:
    """Drift detection: an SPDX line naming a non-Apache license fails."""
    fake = tmp_path / "engine" / "drift.py"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "# SPDX-License-Identifier: GPL-3.0-or-later\n# placeholder\n",
        encoding="utf-8",
    )
    report = auditor.run_audit(tmp_path)
    paths = [p for p, _ in report.drift]
    assert any(
        "drift.py" in p.as_posix() for p in paths
    ), f"audit failed to detect foreign SPDX header; drift={report.drift}"


def test_audit_detects_uncovered_orphan(tmp_path: Path) -> None:
    """A .py file under a non-covered directory must require SPDX."""
    fake = tmp_path / "rogue" / "orphan.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("# no header\n", encoding="utf-8")
    # `rogue/` is not in SCAN_DIRS, so by default it's not scanned. We
    # patch SCAN_DIRS to force a scan and confirm orphan detection.
    original_scan = auditor.SCAN_DIRS
    original_covered = auditor.COVERED_PREFIXES
    auditor.SCAN_DIRS = ("rogue",)
    auditor.COVERED_PREFIXES = ()  # nothing implicitly covered
    try:
        report = auditor.run_audit(tmp_path)
    finally:
        auditor.SCAN_DIRS = original_scan
        auditor.COVERED_PREFIXES = original_covered
    assert any(
        "orphan.py" in p.as_posix() for p in report.missing_spdx
    ), f"audit failed to flag the orphan file; missing={report.missing_spdx}"


def test_audit_main_returns_zero_on_clean_repo() -> None:
    """The CLI entry point exits 0 when the repo is clean."""
    code = auditor.main(["--check"])
    assert code == 0


@pytest.mark.parametrize("scan_dir", list(auditor.SCAN_DIRS))
def test_scan_dirs_actually_exist(scan_dir: str) -> None:
    assert (
        REPO_ROOT / scan_dir
    ).is_dir(), f"audit declares it scans {scan_dir!r} but that directory is missing."
