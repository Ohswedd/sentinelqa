"""07 — discovery.* event parity (Python side).

The canonical fixture is regenerated from
``scripts/export-ts-events-parity.py`` and consumed by both halves.
This test asserts the Python parser accepts the two new event kinds
and surfaces their typed fields.
"""

from __future__ import annotations

from pathlib import Path

from engine.orchestrator.ts_bridge import (
    DiscoveryEndpointEvent,
    DiscoveryPageEvent,
    parse_event,
    parse_events,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests" / "golden" / "ts-events" / "sample.jsonl"


def test_parity_fixture_includes_discovery_events() -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    events = parse_events(lines)
    kinds = [getattr(e, "type", "") for e in events]
    assert "discovery.page" in kinds
    assert "discovery.endpoint" in kinds


def test_discovery_page_event_fields_round_trip() -> None:
    payload = (
        '{"type": "discovery.page", "schema_version": "1.0.0", "seq": 1, '
        '"ts": "2026-05-28T00:00:00.000Z", "url": "http://localhost:3000/", '
        '"status_code": 200, "content_type": "text/html", '
        '"depth": 0, "elapsed_ms": 42, "html": "<html></html>", '
        '"discovered_links": ["http://localhost:3000/login"], '
        '"discovered_script_srcs": ["/a.js"]}'
    )
    event = parse_event(payload)
    assert isinstance(event, DiscoveryPageEvent)
    assert event.url == "http://localhost:3000/"
    assert event.status_code == 200
    assert event.depth == 0
    assert event.discovered_links == ("http://localhost:3000/login",)
    assert event.discovered_script_srcs == ("/a.js",)


def test_discovery_endpoint_event_fields_round_trip() -> None:
    payload = (
        '{"type": "discovery.endpoint", "schema_version": "1.0.0", "seq": 2, '
        '"ts": "2026-05-28T00:00:00.000Z", "method": "POST", '
        '"path": "/api/login", "status_code": 200, "source": "request"}'
    )
    event = parse_event(payload)
    assert isinstance(event, DiscoveryEndpointEvent)
    assert event.method == "POST"
    assert event.path == "/api/login"
    assert event.status_code == 200
    assert event.source == "request"
