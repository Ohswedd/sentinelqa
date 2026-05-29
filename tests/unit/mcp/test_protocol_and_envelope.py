"""Protocol + envelope shape unit tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from sentinelqa_mcp.envelope import (
    AGENT_ENVELOPE_SCHEMA_VERSION,
    AgentEnvelope,
    failure,
    success,
)
from sentinelqa_mcp.protocol import (
    MCP_PROTOCOL_VERSION,
    SUPPORTED_MCP_PROTOCOL_VERSIONS,
    JSONRPCRequest,
    JSONRPCResponse,
    ToolSpec,
)


def test_jsonrpc_request_is_notification_when_id_missing() -> None:
    req = JSONRPCRequest(method="ping")
    assert req.is_notification is True


def test_jsonrpc_request_with_id_is_not_notification() -> None:
    req = JSONRPCRequest(id=1, method="ping")
    assert req.is_notification is False


def test_jsonrpc_response_serialises_minimal_shape() -> None:
    resp = JSONRPCResponse(id=1, result={"ok": True})
    payload = resp.model_dump()
    assert payload["jsonrpc"] == "2.0"


def test_tool_spec_requires_sentinel_prefix() -> None:
    with pytest.raises(ValidationError):
        ToolSpec(name="ping", description="x", inputSchema={"type": "object"})


def test_tool_spec_read_only_meta_round_trip() -> None:
    spec = ToolSpec(
        name="sentinel.ping",
        description="x",
        inputSchema={"type": "object"},
        **{"_meta": {"read_only": True}},
    )
    assert spec.read_only is True
    payload = spec.model_dump(by_alias=True)
    assert payload["_meta"] == {"read_only": True}


def test_envelope_requires_result_or_errors() -> None:
    with pytest.raises(ValidationError):
        AgentEnvelope(tool="sentinel.ping", result=None, errors=())


def test_envelope_success_helper() -> None:
    env = success("sentinel.ping", {"status": "ok"})
    assert env.tool == "sentinel.ping"
    assert env.is_error is False
    assert env.schema_version == AGENT_ENVELOPE_SCHEMA_VERSION


def test_envelope_failure_helper() -> None:
    err = {
        "type": "error",
        "code": "E-CFG-002",
        "exit_code": 2,
        "message": "missing url",
        "suggested_fix": "Pass `url=...`.",
        "context": {},
    }
    env = failure("sentinel.audit", err)
    assert env.is_error is True
    assert env.errors == (err,)


def test_envelope_to_wire_is_sorted_compact() -> None:
    env = success("sentinel.ping", {"status": "ok"})
    raw = env.to_wire()
    parsed = json.loads(raw)
    # Sorted keys ⇒ lexicographic; result must come before tool when sorted.
    assert list(parsed.keys()) == ["errors", "evidence_refs", "result", "schema_version", "tool"]


def test_supported_protocol_versions_includes_canonical() -> None:
    assert MCP_PROTOCOL_VERSION in SUPPORTED_MCP_PROTOCOL_VERSIONS
