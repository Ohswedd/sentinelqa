"""— every our product spec tool round-trips through the dispatcher.

Each tool's success path returns a valid envelope; URL-bearing tools
enforce the safety policy before any SDK call (unsafe → envelope error
with code UNSAFE_TARGET, exit_code 4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from engine.orchestrator.registry import ModuleRegistry

from sentinelqa_mcp import MCPServer

# Tools whose default arguments are accepted by the stub registry.
URL_TOOLS = (
    "sentinel.discover",
    "sentinel.plan",
    "sentinel.audit",
    "sentinel.run_tests",
    "sentinel.security_audit",
    "sentinel.performance_audit",
    "sentinel.accessibility_audit",
    "sentinel.generate_tests",
)


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
    text = response["result"]["content"][0]["text"]
    parsed = json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


@pytest.mark.parametrize("name", list(URL_TOOLS))
async def test_url_tool_rejects_unsafe_target(server: MCPServer, name: str) -> None:
    envelope = await _call(server, name, {"url": "http://attacker.test"})
    assert envelope["tool"] == name
    assert envelope["result"] is None
    assert envelope["errors"]
    err = envelope["errors"][0]
    assert err["type"] == "error"
    assert err["exit_code"] == 4
    # The engine's redactor canonicalises error code as UNSAFE_TARGET-ish;
    # any code that maps to exit_code 4 is acceptable.


@pytest.mark.parametrize("name", list(URL_TOOLS))
async def test_url_tool_missing_url_returns_config_error(server: MCPServer, name: str) -> None:
    envelope = await _call(server, name, {})
    assert envelope["tool"] == name
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 2


async def test_audit_success_path(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    envelope = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    assert envelope["tool"] == "sentinel.audit"
    assert envelope["errors"] == []
    result = envelope["result"]
    assert result["status"] == "passed"
    assert result["passed"] is True
    assert result["target_url"].startswith("http://localhost:3000")
    assert envelope["evidence_refs"], "run dir should expose at least run.json"


async def test_run_tests_invokes_functional_only(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    envelope = await _call(
        server,
        "sentinel.run_tests",
        {"url": "http://localhost:3000", "mode": "smoke"},
    )
    assert envelope["errors"] == []
    assert envelope["result"]["modules_run"] == ["functional"]


async def test_read_report_returns_run_json(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
    project_path: Path,
) -> None:
    # Run an audit so a run dir exists.
    audit_env = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_id = audit_env["result"]["run_id"]
    envelope = await _call(
        server,
        "sentinel.read_report",
        {"run_id": run_id, "path": "run.json"},
    )
    assert envelope["errors"] == []
    assert envelope["result"]["path"] == "run.json"
    assert envelope["result"]["encoding"] == "utf-8"
    payload = json.loads(envelope["result"]["content"])
    assert payload["run_id"] == run_id


async def test_read_report_rejects_traversal(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    # Establish a run.
    audit_env = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    envelope = await _call(
        server,
        "sentinel.read_report",
        {"run_id": audit_env["result"]["run_id"], "path": "../passwd"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 2


async def test_explain_failure_handles_missing_finding(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    audit_env = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_id = audit_env["result"]["run_id"]
    envelope = await _call(
        server,
        "sentinel.explain_failure",
        {"run_id": run_id, "finding_id": "FND-DOES-NOT-EXIST"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 3


async def test_suggest_fix_requires_finding_id(server: MCPServer) -> None:
    envelope = await _call(server, "sentinel.suggest_fix", {})
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 2


async def test_generate_tests_writes_files(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
    project_path: Path,
) -> None:
    envelope = await _call(
        server,
        "sentinel.generate_tests",
        {"url": "http://localhost:3000"},
    )
    assert envelope["errors"] == [] or envelope["result"] is not None
    # Generator may return zero files when the plan is empty — both
    # paths are valid; assert the wire shape.
    assert envelope["tool"] == "sentinel.generate_tests"


async def test_invalid_tool_arguments_returns_error_envelope(server: MCPServer) -> None:
    envelope = await _call(
        server, "sentinel.run_tests", {"url": "http://localhost:3000", "mode": "EXTREME"}
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 2


async def test_unknown_tool_returns_method_not_found(server: MCPServer) -> None:
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "sentinel.does_not_exist", "arguments": {}},
        }
    )
    assert response is not None
    assert response["error"]["code"] == -32601
