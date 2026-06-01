"""Coverage-fill tests for the dep-scan adapters."""

from __future__ import annotations

import json
from pathlib import Path

from modules.security.checks.deps import (
    RunResult,
    _default_run,
    _npm_audit_issues,
    _osv_issues,
    _pip_audit_issues,
    _severity_from_advisory,
    run_dependency_scan,
)


def test_severity_label_map() -> None:
    assert _severity_from_advisory("CRITICAL") == "critical"
    assert _severity_from_advisory("HIGH") == "high"
    assert _severity_from_advisory("moderate") == "medium"
    assert _severity_from_advisory("low") == "low"
    assert _severity_from_advisory("info") == "info"
    assert _severity_from_advisory("") == "info"
    assert _severity_from_advisory("unknown") == "medium"


def test_pip_audit_handles_payload_list() -> None:
    payload = [
        {
            "name": "flask",
            "version": "2.0.0",
            "vulns": [{"id": "X", "description": "", "fix_versions": [], "severity": "high"}],
        }
    ]
    issues = list(_pip_audit_issues(payload))
    assert len(issues) == 1


def test_pip_audit_returns_empty_for_unknown_shape() -> None:
    assert list(_pip_audit_issues({"oops": 1})) == []
    assert list(_pip_audit_issues("string")) == []


def test_npm_audit_skips_non_dict_via() -> None:
    payload = {
        "vulnerabilities": {
            "x": {"severity": "low", "range": "*", "via": ["string-not-dict"]},
        }
    }
    issues = list(_npm_audit_issues(payload))
    assert len(issues) == 1


def test_npm_audit_handles_no_vulns() -> None:
    assert list(_npm_audit_issues({})) == []
    assert list(_npm_audit_issues({"vulnerabilities": "nope"})) == []


def test_osv_issues_parses_results() -> None:
    payload = {
        "results": [
            {
                "packages": [
                    {
                        "package": {"name": "x", "version": "1"},
                        "vulnerabilities": [
                            {"id": "GHSA-1", "summary": "bad"},
                            {"id": "GHSA-2"},
                        ],
                    }
                ]
            }
        ]
    }
    issues = list(_osv_issues(payload))
    assert len(issues) == 2


def test_osv_issues_handles_empty_payload() -> None:
    assert list(_osv_issues({})) == []
    assert list(_osv_issues({"results": "nope"})) == []


def test_dep_scan_aggregates_multiple_adapters(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n"
        "  dependency_scanners:\n"
        "    pip_audit: true\n"
        "    npm_audit: true\n"
        "    osv_scanner: true\n"
    )
    ctx = make_ctx(security_block=block)
    (tmp_path / "requirements.txt").write_text("a==1\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        if cmd[0] == "pip-audit":
            return 1, json.dumps({"dependencies": []}), ""
        if cmd[0] == "npm":
            return 1, json.dumps({"vulnerabilities": {}}), ""
        return 0, json.dumps({"results": []}), ""

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert result.targets_scanned == 3
    assert result.issues == ()


def test_default_run_returns_tuple(tmp_path: Path) -> None:
    rc, stdout, stderr = _default_run(["echo", "hello"], tmp_path)
    assert rc == 0
    assert "hello" in stdout


def test_dep_scan_unknown_exit_code(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(security_block=block)
    (tmp_path / "requirements.txt").write_text("a==1\n", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 99, "", "boom"

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert result.issues == ()


def test_dep_scan_non_json_output(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(security_block=block)
    (tmp_path / "requirements.txt").write_text("a==1\n", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 0, "not json", ""

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert result.issues == ()
