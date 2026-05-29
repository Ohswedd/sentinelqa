"""Task 18.03 — byte-locked agent envelope goldens.

Pin the wire shape of the envelope for the three response classes:

- A read-only success (`sentinel.ping`).
- A safety-blocked failure (`sentinel.audit` with an unsafe URL).
- A configuration-error failure (`sentinel.audit` with no URL).

Set ``SENTINELQA_UPDATE_GOLDENS=1`` (or ``make update-goldens``) to
regenerate after an intentional envelope shape change. ADR-0023 bumps
``AGENT_ENVELOPE_SCHEMA_VERSION`` when the shape changes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sentinelqa_mcp import AgentEnvelope, MCPServer

GOLDEN_DIR = Path(__file__).parent / "expected"
UPDATE_ENV: str = "SENTINELQA_UPDATE_GOLDENS"


async def _envelope(server: MCPServer, name: str, arguments: dict[str, Any]) -> AgentEnvelope:
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
    return AgentEnvelope.model_validate(json.loads(text))


def _read_or_write_golden(name: str, actual_bytes: bytes) -> None:
    golden_path = GOLDEN_DIR / name
    if os.environ.get(UPDATE_ENV):
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_bytes(actual_bytes)
        return
    assert (
        golden_path.exists()
    ), f"missing golden {golden_path.name}; run with {UPDATE_ENV}=1 to create."
    expected = golden_path.read_bytes()
    assert (
        actual_bytes == expected
    ), f"envelope drift vs {golden_path.name}; run with {UPDATE_ENV}=1 to refresh."


def _stable_serialise(envelope: AgentEnvelope) -> bytes:
    return (envelope.to_wire() + "\n").encode("utf-8")


@pytest.mark.parametrize(
    "name,arguments,golden",
    [
        ("sentinel.ping", {}, "ping_success.json"),
    ],
)
async def test_envelope_goldens_pure(
    server: MCPServer, name: str, arguments: dict[str, Any], golden: str
) -> None:
    envelope = await _envelope(server, name, arguments)
    _read_or_write_golden(golden, _stable_serialise(envelope))


async def test_envelope_unsafe_target_shape(server: MCPServer) -> None:
    envelope = await _envelope(server, "sentinel.audit", {"url": "http://attacker.test"})
    # Shape — not byte-equal, because the audit log path inside the error
    # context varies by ``tmp_path``. Validate just the stable fields.
    assert envelope.tool == "sentinel.audit"
    assert envelope.result is None
    assert len(envelope.errors) == 1
    err = envelope.errors[0]
    assert err["exit_code"] == 4
    assert err["type"] == "error"
    assert err["message"]


async def test_envelope_config_error_shape(server: MCPServer) -> None:
    envelope = await _envelope(server, "sentinel.audit", {})
    assert envelope.tool == "sentinel.audit"
    assert envelope.result is None
    assert envelope.errors[0]["exit_code"] == 2


def test_envelope_schema_validates_success() -> None:
    """The envelope JSON Schema accepts a well-formed success envelope."""

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "shared-schema"
        / "agent-envelope.schema.json"
    )
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = AgentEnvelope(
        tool="sentinel.ping",
        result={"status": "ok"},
        errors=(),
        evidence_refs=("run.json",),
    ).model_dump(mode="json")
    jsonschema.validate(payload, schema)
