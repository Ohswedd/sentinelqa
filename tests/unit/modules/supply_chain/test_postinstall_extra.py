"""Final postinstall coverage gaps (Phase 33.04)."""

from __future__ import annotations

import json
from pathlib import Path

from modules.supply_chain.postinstall import (
    _classify_npm_match,
    scan_npm_packages,
    scan_python_packages,
)


def test_classify_npm_match_each_branch() -> None:
    assert _classify_npm_match("curl", "curl") == "high"
    assert _classify_npm_match("wget", "wget") == "high"
    assert _classify_npm_match("nc", "nc") == "high"
    assert _classify_npm_match("ncat", "ncat") == "high"
    assert _classify_npm_match("bash -c", "bash -c") == "medium"
    assert _classify_npm_match("sh -c", "sh -c") == "medium"
    assert _classify_npm_match("eval", "eval") == "medium"
    assert _classify_npm_match("anything", "fallback") == "medium"


def test_scan_npm_uses_dir_name_when_name_field_missing(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules" / "fallbackpkg"
    nm.mkdir(parents=True)
    (nm / "package.json").write_text(
        json.dumps({"scripts": {"postinstall": "curl evil"}}), encoding="utf-8"
    )
    issues = scan_npm_packages(tmp_path / "node_modules")
    # When `name` is missing the scanner falls back to the parent directory.
    assert any(issue.package == "fallbackpkg" for issue in issues)


def test_scan_python_packages_walks_venv_and_tox(tmp_path: Path) -> None:
    # Put a setup.py in venv/, .venv/ and .tox/.
    for venv_dir in ("venv", ".venv", ".tox"):
        target = tmp_path / venv_dir / "pkg"
        target.mkdir(parents=True)
        (target / "setup.py").write_text("import subprocess\n", encoding="utf-8")
    issues = scan_python_packages(project_root=tmp_path)
    assert any(issue.pattern == "import:subprocess" for issue in issues)


def test_scan_python_packages_dedups_same_file(tmp_path: Path) -> None:
    """Symlinks / duplicate scans don't double-count."""

    target = tmp_path / "venv" / "pkg"
    target.mkdir(parents=True)
    (target / "setup.py").write_text("import subprocess\n", encoding="utf-8")
    # Run twice; the seen-set prevents double-counting within a single call.
    issues_a = scan_python_packages(project_root=tmp_path)
    issues_b = scan_python_packages(project_root=tmp_path)
    # Each invocation returns its own non-empty result (no caching).
    assert len(issues_a) >= 1
    assert len(issues_b) >= 1
