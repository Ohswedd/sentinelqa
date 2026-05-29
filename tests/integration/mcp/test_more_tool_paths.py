"""More tool-path coverage for discover/plan/read_report/verify_fix/explain/suggest."""

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


async def test_discover_returns_graph_id(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
    httpserver: Any,
) -> None:
    # Configure the project's allowed_hosts to include the server, then
    # discover. The server returns an empty page so the graph is minimal.
    httpserver.expect_request("/").respond_with_data("<html><body><p>hi</p></body></html>")
    # The project config already allows localhost; httpserver binds to
    # 127.0.0.1, which the safety policy treats as local.
    url = httpserver.url_for("/")
    envelope = await _call(server, "sentinel.discover", {"url": url})
    assert envelope["errors"] == []
    assert envelope["result"]["graph_id"].startswith("DG-")
    assert envelope["result"]["route_count"] >= 0


async def test_plan_returns_plan_id(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
    httpserver: Any,
) -> None:
    httpserver.expect_request("/").respond_with_data("<html><body></body></html>")
    url = httpserver.url_for("/")
    envelope = await _call(server, "sentinel.plan", {"url": url})
    assert envelope["errors"] == []
    assert envelope["result"]["plan_id"].startswith("PLN-")


async def test_read_report_binary_falls_back_to_hex(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    binary = run_dir / "blob.bin"
    binary.write_bytes(b"\xff\xfe\xfd")
    envelope = await _call(
        server,
        "sentinel.read_report",
        {"run_id": audit["result"]["run_id"], "path": "blob.bin"},
    )
    assert envelope["result"]["encoding"] == "hex"
    assert envelope["result"]["content"] == "fffefd"


async def test_read_report_truncates_large_file(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    big = run_dir / "big.txt"
    big.write_text("a" * (1024 * 1024))  # 1 MiB, well over the 256 KiB cap
    envelope = await _call(
        server,
        "sentinel.read_report",
        {"run_id": audit["result"]["run_id"], "path": "big.txt"},
    )
    assert envelope["result"]["truncated"] is True
    assert envelope["result"]["byte_count"] == 256 * 1024


async def test_explain_failure_handles_corrupt_findings(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_dir = Path(audit["result"]["run_dir"])
    (run_dir / "findings.json").write_text("not-json", encoding="utf-8")
    envelope = await _call(
        server,
        "sentinel.explain_failure",
        {"run_id": audit["result"]["run_id"], "finding_id": "FND-X"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 3


async def test_verify_fix_uses_url_when_supplied(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    envelope = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": audit["result"]["run_id"], "url": "http://localhost:3001"},
    )
    # Even without findings the loop should succeed.
    assert envelope["errors"] == []
    assert envelope["result"]["decision"] in {
        "fix_verified",
        "still_failing",
        "regressed",
        "partial",
    }


async def test_verify_fix_rejects_unsafe_url(server: MCPServer) -> None:
    envelope = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": "RUN-ABC123ABCDEF", "url": "http://attacker.test"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] == 4
