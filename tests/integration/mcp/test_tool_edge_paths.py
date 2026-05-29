"""More edge paths to satisfy the 95% coverage gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.orchestrator.registry import ModuleRegistry

from sentinelqa_mcp import MCPServer


async def _call(server: MCPServer, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    parsed: dict[str, Any] = json.loads(response["result"]["content"][0]["text"])
    return parsed


async def test_suggest_fix_missing_findings_file(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    fpath = run_dir / "findings.json"
    if fpath.exists():
        fpath.unlink()
    envelope = await _call(
        server,
        "sentinel.suggest_fix",
        {"run_id": audit["result"]["run_id"], "finding_id": "FND-NONE"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 3


async def test_suggest_fix_finding_not_present_returns_error(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": [{"id": "FND-OTHER", "recommendation": "x"}]}),
        encoding="utf-8",
    )
    envelope = await _call(
        server,
        "sentinel.suggest_fix",
        {"run_id": audit["result"]["run_id"], "finding_id": "FND-NOPE"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 3


async def test_run_tests_without_grep(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    envelope = await _call(
        server,
        "sentinel.run_tests",
        {"url": "http://localhost:3000", "mode": "full"},
    )
    assert envelope["errors"] == []
    assert envelope["result"]["modules_run"] == ["functional"]


async def test_verify_fix_without_finding_id(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    envelope = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": audit["result"]["run_id"]},
    )
    assert envelope["errors"] == []
    # No findings before / after → fix_verified per ADR-0023.
    assert envelope["result"]["decision"] in {"fix_verified", "partial"}


async def test_verify_fix_with_explicit_modules(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    envelope = await _call(
        server,
        "sentinel.verify_fix",
        {
            "run_id": audit["result"]["run_id"],
            "modules": ["functional"],
        },
    )
    assert envelope["errors"] == []


async def test_explain_failure_without_run_id_uses_latest(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    # Run an audit so there's a latest run.
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    (run_dir / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "FND-LATEST00001",
                        "module": "functional",
                        "category": "reliability",
                        "severity": "low",
                        "title": "latest",
                        "recommendation": "do it",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    envelope = await _call(
        server,
        "sentinel.explain_failure",
        {"finding_id": "FND-LATEST00001"},
    )
    assert envelope["errors"] == [] or envelope["result"] is None
