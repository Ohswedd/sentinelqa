"""Integration tests — dependency scan adapters."""

from __future__ import annotations

import json
from pathlib import Path

from modules.security.checks.deps import RunResult, run_dependency_scan
from tests.integration.modules.security.conftest import make_ctx


def test_pip_audit_full_flow(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    block = (
        "security:\n" "  dependency_scanners:\n" "    pip_audit: true\n" "    npm_audit: false\n"
    )
    ctx = make_ctx(
        base_url="http://localhost:9999",
        tmp_path=tmp_path,
        security_block=block,
    )
    (tmp_path / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
    monkeypatch.setattr("modules.security.checks.deps._binary_available", lambda name: True)
    payload = {
        "dependencies": [
            {
                "name": "requests",
                "version": "2.0.0",
                "vulns": [
                    {
                        "id": "CVE-2018-1000007",
                        "description": "Authorization header on redirect",
                        "fix_versions": ["2.20.0"],
                        "severity": "HIGH",
                    }
                ],
            }
        ]
    }

    def fake_run(cmd, cwd) -> RunResult:  # type: ignore[no-untyped-def]
        return 1, json.dumps(payload), ""

    try:
        result = run_dependency_scan(ctx, project_root=tmp_path, run=fake_run)
    finally:
        ctx.client.close()
    assert any(i.rule_id == "SEC-DEPS-VULNERABLE" and i.severity == "high" for i in result.issues)
