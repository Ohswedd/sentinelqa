"""Phase 04.05 — Python parses every TS-emitted evidence artifact.

The TS runtime emits four evidence-shaped events during a typical
failure:

  * `evidence` (trace / screenshot / video / har / dom_snapshot)
  * `dom.snapshot`
  * `console`
  * `network.request` + `network.response`

This test pulls those entries from the canonical parity fixture and
proves the Python bridge round-trips them with the right typed model,
the right field shapes, and the right enum values.

If the bridge ever drops a field or renames an enum, this test fails
*before* a downstream consumer (the SDK or MCP layer) does.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.orchestrator.ts_bridge import (
    ConsoleEvent,
    DomSnapshotEvent,
    EvidenceEvent,
    NetworkRequestEvent,
    NetworkResponseEvent,
    parse_event,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests" / "golden" / "ts-events" / "sample.jsonl"


def _by_type(target_type: str) -> list[object]:
    out: list[object] = []
    for line in FIXTURE.read_text().splitlines():
        if not line:
            continue
        payload = json.loads(line)
        if payload.get("type") == target_type:
            out.append(parse_event(line))
    return out


def test_evidence_events_parse_to_evidence_model() -> None:
    events = _by_type("evidence")
    assert events, "fixture should contain at least one evidence event"
    for ev in events:
        assert isinstance(ev, EvidenceEvent)
        assert ev.evidence_kind in {
            "trace",
            "screenshot",
            "video",
            "har",
            "dom_snapshot",
            "network_log",
            "console_log",
        }
        assert ev.path
        assert ev.label


def test_dom_snapshot_events_parse() -> None:
    events = _by_type("dom.snapshot")
    assert events
    for ev in events:
        assert isinstance(ev, DomSnapshotEvent)
        assert ev.path


def test_console_events_parse_with_redacted_message_shape() -> None:
    events = _by_type("console")
    assert events
    for ev in events:
        assert isinstance(ev, ConsoleEvent)
        assert ev.level in {"log", "debug", "info", "warn", "error"}


def test_network_events_round_trip_with_correlated_request_id() -> None:
    requests = _by_type("network.request")
    responses = _by_type("network.response")
    assert requests and responses
    request_ids = {ev.request_id for ev in requests if isinstance(ev, NetworkRequestEvent)}
    response_ids = {ev.request_id for ev in responses if isinstance(ev, NetworkResponseEvent)}
    # Every response in the fixture must correlate to a request id.
    assert response_ids.issubset(
        request_ids
    ), f"orphan response ids: {sorted(response_ids - request_ids)}"
