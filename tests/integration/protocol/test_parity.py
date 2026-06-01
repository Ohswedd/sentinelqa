"""Python half of the TS-events parity contract.

The TS half lives in
``packages/ts-runtime/src/__tests__/protocol.parity.test.ts``. Both
sides load the same JSONL fixture
(``tests/golden/ts-events/sample.jsonl``) and assert their parsers
agree event-by-event.

Drift gates:

1. ``--check`` mode of the export script (the fixture is current).
2. Every event in the fixture is one of the 14 TsEvent kinds and
 round-trips through :func:`parse_event` without raising.
3. The on-disk JSON Schema validates the rendered fixture.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from engine.orchestrator.ts_bridge import (
    PROTOCOL_VERSION,
    ProtocolParseError,
    parse_event,
    parse_events,
    stream_events,
)
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests" / "golden" / "ts-events" / "sample.jsonl"
SCHEMA = REPO_ROOT / "packages" / "shared-schema" / "ts-events.schema.json"
SCRIPT = REPO_ROOT / "scripts" / "export-ts-events-parity.py"


@pytest.fixture(scope="module")
def lines() -> list[str]:
    return [line for line in FIXTURE.read_text().splitlines() if line]


@pytest.fixture(scope="module")
def schema() -> dict[str, object]:
    data: dict[str, object] = json.loads(SCHEMA.read_text())
    return data


def test_parity_fixture_is_current() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"parity fixture stale: {result.stderr}. "
        f"Run `python scripts/export-ts-events-parity.py`."
    )


def test_protocol_version_matches() -> None:
    """Python's PROTOCOL_VERSION must match the TS constant."""

    ts_const = (REPO_ROOT / "packages" / "ts-runtime" / "src" / "protocol.ts").read_text()
    assert f"PROTOCOL_VERSION = '{PROTOCOL_VERSION}'" in ts_const, (
        "TS PROTOCOL_VERSION drifted from Python PROTOCOL_VERSION; "
        "bump both halves together and write a migration ADR."
    )


def test_every_event_kind_appears(lines: list[str]) -> None:
    """The fixture must cover every TsEvent kind so we can prove parity."""

    expected = {
        "run.start",
        "run.end",
        "test.start",
        "test.end",
        "step.start",
        "step.end",
        "evidence",
        "network.request",
        "network.response",
        "console",
        "dom.snapshot",
        "module.event",
        "log",
        "error",
    }
    types = {json.loads(line)["type"] for line in lines}
    missing = expected - types
    assert not missing, f"fixture is missing event kinds: {sorted(missing)}"


def test_python_parses_each_line(lines: list[str]) -> None:
    events = parse_events(lines)
    assert len(events) == len(lines)
    types = [ev.type for ev in events]  # type: ignore[attr-defined]
    assert types[0] == "run.start"
    assert types[-1] == "run.end"


def test_schema_validates_each_line(lines: list[str], schema: dict[str, object]) -> None:
    """JSON Schema is the wire contract — every fixture line must satisfy it."""

    validator = Draft202012Validator(schema)
    for n, line in enumerate(lines, start=1):
        payload = json.loads(line)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        assert not errors, (
            f"line {n} (type={payload.get('type')!r}) violates schema:\n  - "
            + "\n  - ".join(err.message for err in errors)
        )


def test_unknown_type_raises_protocol_error() -> None:
    line = json.dumps(
        {
            "type": "totally.unknown",
            "schema_version": PROTOCOL_VERSION,
            "seq": 1,
            "ts": "2026-05-28T00:00:00Z",
        }
    )
    with pytest.raises(ProtocolParseError, match="unknown event type"):
        parse_event(line)


def test_missing_required_field_raises() -> None:
    line = json.dumps(
        {
            "type": "test.end",
            "schema_version": PROTOCOL_VERSION,
            "seq": 1,
            "ts": "2026-05-28T00:00:00Z",
            "test_id": "t",
            "duration_ms": 0,
            # status missing
            "retries": 0,
        }
    )
    with pytest.raises(ProtocolParseError):
        parse_event(line)


def test_invalid_json_raises() -> None:
    with pytest.raises(ProtocolParseError, match="invalid JSON"):
        parse_event("{not json}")


def test_empty_line_raises() -> None:
    with pytest.raises(ProtocolParseError, match="empty event line"):
        parse_event("")


def test_stream_events_parses_byte_lines() -> None:
    """`stream_events` consumes an async iterable of bytes/str."""

    async def fake_reader() -> object:  # pragma: no cover — driver
        for line in [
            b'{"type":"run.start","schema_version":"1.0.0","seq":1,"ts":"2026-05-28T00:00:00Z","run_id":"r","target":"x","started_at":"2026-05-28T00:00:00Z"}\n',
            b"\n",  # heartbeat
            b'{"type":"run.end","schema_version":"1.0.0","seq":2,"ts":"2026-05-28T00:00:01Z","run_id":"r","finished_at":"2026-05-28T00:00:01Z","status":"passed","tests_total":0,"tests_failed":0}\n',
        ]:
            yield line

    async def driver() -> list[str]:
        results: list[str] = []
        async for ev in stream_events(fake_reader()):
            results.append(ev.type)  # type: ignore[attr-defined]
        return results

    assert asyncio.run(driver()) == ["run.start", "run.end"]
