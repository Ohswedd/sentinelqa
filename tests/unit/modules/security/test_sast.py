"""Unit tests for the SAST adapter (Phase 13.09)."""

from __future__ import annotations

import json
from pathlib import Path

from modules.security.checks.deps import RunResult
from modules.security.checks.sast import run_sast


def test_sast_skipped_when_disabled(make_ctx, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx()
    result = run_sast(ctx, project_root=tmp_path)
    assert result.skipped is True
    assert result.skipped_reason == "security.dependency_scanners.semgrep is false"


def test_sast_skipped_when_binary_missing(make_ctx, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  checks:\n    sast: true\n" "  dependency_scanners:\n    semgrep: true\n"
    )
    ctx = make_ctx(security_block=block)
    monkeypatch.setattr("modules.security.checks.sast._semgrep_available", lambda: False)
    result = run_sast(ctx, project_root=tmp_path)
    assert result.skipped is True
    assert "PATH" in (result.skipped_reason or "")


def test_sast_parses_semgrep_output(make_ctx, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  checks:\n    sast: true\n" "  dependency_scanners:\n    semgrep: true\n"
    )
    ctx = make_ctx(security_block=block)
    monkeypatch.setattr("modules.security.checks.sast._semgrep_available", lambda: True)
    payload = {
        "results": [
            {
                "check_id": "python.lang.security.injection",
                "path": "src/app.py",
                "start": {"line": 42},
                "extra": {
                    "message": "Potential injection",
                    "severity": "WARNING",
                },
            }
        ]
    }

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 1, json.dumps(payload), ""

    result = run_sast(ctx, project_root=tmp_path, run=fake_run)
    assert result.skipped is False
    assert any(i.rule_id == "SEC-SAST-FINDING" for i in result.issues)
