"""Unit tests for the dependency-scanner adapters."""

from __future__ import annotations

import json
from pathlib import Path

from modules.security.checks.deps import RunResult, run_dependency_scan


def test_pip_audit_adapter_no_lockfile(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(security_block=block)
    # Pretend pip-audit is available so we exercise the lockfile branch.
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        raise AssertionError("run should not be called without a lockfile")

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert result.targets_scanned == 1
    assert result.issues == ()


def test_pip_audit_adapter_parses_vulns(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(security_block=block)
    (tmp_path / "requirements.txt").write_text("flask==2.0.0\n", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)
    payload = {
        "dependencies": [
            {
                "name": "flask",
                "version": "2.0.0",
                "vulns": [
                    {
                        "id": "GHSA-xxxx-yyyy-zzzz",
                        "description": "Open redirect",
                        "fix_versions": ["2.0.1"],
                        "severity": "MODERATE",
                    }
                ],
            }
        ]
    }

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 1, json.dumps(payload), ""

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert any(i.rule_id == "SEC-DEPS-VULNERABLE" for i in result.issues)
    issue = next(i for i in result.issues if "GHSA-" in i.title)
    assert issue.severity == "medium"


def test_npm_audit_adapter_parses_vulns(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: false\n" "    npm_audit: true\n"
    )
    ctx = make_ctx(security_block=block)
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)
    payload = {
        "vulnerabilities": {
            "left-pad": {
                "severity": "high",
                "range": "<1.3.0",
                "via": [{"url": "https://npmjs.com/advisories/1", "title": "left-pad weirdness"}],
            }
        }
    }

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 1, json.dumps(payload), ""

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert any(i.rule_id == "SEC-DEPS-VULNERABLE" and i.severity == "high" for i in result.issues)


def test_dep_scan_missing_tool_reports_skip(tmp_path: Path, monkeypatch, make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(security_block=block)
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: False)
    called = {"n": 0}

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        called["n"] += 1
        return 0, "", ""

    result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    assert called["n"] == 0
    assert result.targets_scanned == 1
    assert result.issues == ()
