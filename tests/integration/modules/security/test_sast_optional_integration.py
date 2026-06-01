"""Integration tests — semgrep SAST adapter."""

from __future__ import annotations

import json
from pathlib import Path

from modules.security.checks.deps import RunResult
from modules.security.checks.sast import run_sast
from tests.integration.modules.security.conftest import make_ctx


def test_sast_full_pass_when_enabled(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  checks:\n    sast: true\n" "  dependency_scanners:\n    semgrep: true\n"
    )
    ctx = make_ctx(
        base_url="http://localhost:9999",
        tmp_path=tmp_path,
        security_block=block,
    )
    monkeypatch.setattr("modules.security.checks.sast._semgrep_available", lambda: True)
    payload = {
        "results": [
            {
                "check_id": "go.lang.security.audit.sqli",
                "path": "internal/db.go",
                "start": {"line": 33},
                "extra": {"message": "Possible SQLi", "severity": "ERROR"},
            }
        ]
    }

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 1, json.dumps(payload), ""

    try:
        result = run_sast(ctx, project_root=tmp_path, run=fake_run)
    finally:
        ctx.client.close()
    assert result.skipped is False
    assert any(i.rule_id == "SEC-SAST-FINDING" for i in result.issues)


def test_sast_off_by_default(tmp_path: Path) -> None:
    ctx = make_ctx(
        base_url="http://localhost:9999",
        tmp_path=tmp_path,
    )
    try:
        result = run_sast(ctx, project_root=tmp_path)
    finally:
        ctx.client.close()
    assert result.skipped is True
