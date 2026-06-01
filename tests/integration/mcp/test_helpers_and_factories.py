"""Coverage for the audit helpers, factory, and the read/suggest/explain paths."""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.registry import ModuleRegistry

from sentinelqa_mcp import MCPServer, build_default_server
from sentinelqa_mcp.tools import SentinelToolset
from sentinelqa_mcp.tools._audit_helpers import (
    parse_optional_modules,
    safe_relative,
)


def test_parse_optional_modules_returns_none_when_absent() -> None:
    assert parse_optional_modules({}) is None


def test_parse_optional_modules_string_singleton() -> None:
    assert parse_optional_modules({"modules": "functional"}) == ("functional",)


def test_parse_optional_modules_empty_string_yields_none() -> None:
    assert parse_optional_modules({"modules": ""}) is None


def test_parse_optional_modules_strips_blanks() -> None:
    assert parse_optional_modules({"modules": ["functional", " ", ""]}) == ("functional",)


def test_parse_optional_modules_rejects_non_iterable() -> None:
    assert parse_optional_modules({"modules": 7}) is None


def test_safe_relative_outside_root_returns_absolute(tmp_path: Path) -> None:
    outside = tmp_path.parent / "x"
    assert safe_relative(outside, tmp_path).startswith("/")


def test_safe_relative_inside_root(tmp_path: Path) -> None:
    inner = tmp_path / "a" / "b.txt"
    inner.parent.mkdir(parents=True)
    inner.write_text("x")
    assert safe_relative(inner, tmp_path) == "a/b.txt"


def test_build_default_server_constructs_canonical_registry(tmp_path: Path) -> None:
    (tmp_path / "sentinel.config.yaml").write_text(
        "version: 1\n"
        "project:\n  name: p\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts:\n    - localhost\n"
        "modules:\n  functional: true\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    server = build_default_server(project_path=tmp_path)
    assert isinstance(server, MCPServer)
    assert len(server.toolset) == 16


async def _call_envelope(
    server: MCPServer, name: str, arguments: dict[str, object]
) -> dict[str, object]:
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
    return json.loads(text)  # type: ignore[no-any-return]


async def test_explain_failure_returns_finding_when_present(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    # Run an audit so a run dir exists.
    audit = await _call_envelope(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_id = audit["result"]["run_id"]  # type: ignore[index]
    # Synthesise a findings.json with one entry so explain_failure has
    # something to return.
    run_dir = Path(audit["result"]["run_dir"])  # type: ignore[index]
    findings_path = run_dir / "findings.json"
    findings_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "run_id": run_id,
                "findings": [
                    {
                        "id": "FND-MANUAL000001",
                        "module": "functional",
                        "category": "reliability",
                        "severity": "low",
                        "title": "manual",
                        "recommendation": "Try X.",
                        "suggested_fix": "Apply Y.",
                        "evidence_paths": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    explain = await _call_envelope(
        server,
        "sentinel.explain_failure",
        {"run_id": run_id, "finding_id": "FND-MANUAL000001"},
    )
    assert explain["errors"] == []
    assert explain["result"]["finding"]["id"] == "FND-MANUAL000001"  # type: ignore[index]


async def test_suggest_fix_returns_recommendation_when_present(
    server: MCPServer,
    stub_functional_registry: ModuleRegistry,
) -> None:
    audit = await _call_envelope(server, "sentinel.audit", {"url": "http://localhost:3000"})
    run_id = audit["result"]["run_id"]  # type: ignore[index]
    run_dir = Path(audit["result"]["run_dir"])  # type: ignore[index]
    (run_dir / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "FND-SUGG000001AA",
                        "recommendation": "Set Secure on the cookie.",
                        "suggested_fix": "cookie.set(secure=True)",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    suggestion = await _call_envelope(
        server,
        "sentinel.suggest_fix",
        {"run_id": run_id, "finding_id": "FND-SUGG000001AA"},
    )
    assert suggestion["errors"] == []
    assert suggestion["result"]["recommendation"] == "Set Secure on the cookie."  # type: ignore[index]


async def test_suggest_fix_missing_run(server: MCPServer) -> None:
    envelope = await _call_envelope(
        server,
        "sentinel.suggest_fix",
        {"run_id": "RUN-NOPE00000000", "finding_id": "FND-X"},
    )
    assert envelope["result"] is None
    assert envelope["errors"][0]["exit_code"] in {3, 7}  # type: ignore[index]


async def test_explain_failure_missing_run(server: MCPServer) -> None:
    envelope = await _call_envelope(
        server,
        "sentinel.explain_failure",
        {"run_id": "RUN-NOPE00000000", "finding_id": "FND-X"},
    )
    assert envelope["result"] is None


async def test_performance_audit_with_options(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    envelope = await _call_envelope(
        server,
        "sentinel.performance_audit",
        {"url": "http://localhost:3000", "routes": ["/", "/about"], "samples": 3},
    )
    assert envelope["tool"] == "sentinel.performance_audit"


async def test_accessibility_audit_with_options(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    envelope = await _call_envelope(
        server,
        "sentinel.accessibility_audit",
        {"url": "http://localhost:3000", "routes": ["/"], "axe_tags": ["wcag2aa"]},
    )
    assert envelope["tool"] == "sentinel.accessibility_audit"


async def test_security_audit_with_checks(
    server: MCPServer, stub_functional_registry: ModuleRegistry
) -> None:
    envelope = await _call_envelope(
        server,
        "sentinel.security_audit",
        {"url": "http://localhost:3000", "checks": ["headers", "cookies"]},
    )
    assert envelope["tool"] == "sentinel.security_audit"


def test_toolset_register_duplicate_rejected() -> None:
    from sentinelqa_mcp.tools.ping import PingTool

    toolset = SentinelToolset()
    toolset.register(PingTool())
    try:
        toolset.register(PingTool())
    except ValueError as exc:
        assert "already" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_toolset_iter_and_len() -> None:
    toolset = SentinelToolset.with_defaults()
    names_iter = [tool.spec.name for tool in toolset]
    assert names_iter == list(toolset.names())
    assert len(toolset) == len(names_iter)


async def test_dispatcher_rejects_jsonrpc_version_one(server: MCPServer) -> None:
    bad = await server.dispatch({"jsonrpc": "1.0", "id": 1, "method": "ping"})
    assert bad is not None
    assert bad["error"]["code"] == -32600


async def test_dispatcher_rejects_positional_params(server: MCPServer) -> None:
    bad = await server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1, 2]})
    assert bad is not None
    assert bad["error"]["code"] == -32602
