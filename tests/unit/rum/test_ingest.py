# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the RUM JSONL ingest path."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.rum import (
    RUM_EVENT_KINDS,
    RumIngestError,
    ingest_jsonl,
    parse_event,
)


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def test_event_kinds_includes_required() -> None:
    for required in {
        "run.start",
        "run.end",
        "page.view",
        "page.error",
        "network.request",
        "network.response",
        "network.failure",
        "console",
        "user.action",
    }:
        assert required in RUM_EVENT_KINDS


def test_parse_event_round_trips_envelope() -> None:
    raw = {
        "schema_version": "1",
        "type": "page.view",
        "seq": 7,
        "ts": "2026-06-02T12:00:00Z",
        "route": "/home",
    }
    event = parse_event(raw)
    assert event.type == "page.view"
    assert event.seq == 7
    assert event.payload == {"route": "/home"}
    assert event.is_known


def test_parse_event_tolerates_unknown_type() -> None:
    event = parse_event({"type": "mystery"})
    assert not event.is_known
    assert event.type == "mystery"


def test_ingest_creates_run_dir(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "run.start",
                "seq": 1,
                "ts": "2026-06-02T12:00:00Z",
            },
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 2,
                "ts": "2026-06-02T12:00:01Z",
                "route": "/home",
            },
            {
                "schema_version": "1",
                "type": "run.end",
                "seq": 3,
                "ts": "2026-06-02T12:00:02Z",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert result.run_dir.is_dir()
    assert (result.run_dir / "run.json").is_file()
    assert (result.run_dir / "events.jsonl").is_file()
    assert (result.run_dir / "findings.json").is_file()
    assert result.events_processed == 3
    assert result.parse_errors == 0
    assert result.findings_emitted == 0


def test_page_errors_become_findings(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.error",
                "seq": 1,
                "ts": "2026-06-02T12:00:00Z",
                "route": "/checkout",
                "message": "Cannot read property 'price' of undefined",
            },
            {
                "schema_version": "1",
                "type": "page.error",
                "seq": 2,
                "ts": "2026-06-02T12:00:01Z",
                "route": "/checkout",
                "message": "Cannot read property 'price' of undefined",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    # Duplicate (route, message) pair collapses to one finding.
    assert result.findings_emitted == 1

    findings_payload = json.loads((result.run_dir / "findings.json").read_text())
    assert findings_payload["count"] == 1
    finding = findings_payload["findings"][0]
    assert finding["severity"] == "high"
    assert finding["location"]["route"] == "/checkout"


def test_run_json_summary_matches_findings(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.error",
                "seq": 1,
                "ts": "2026-06-02T12:00:00Z",
                "route": "/x",
                "message": "boom",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    run_json = json.loads((result.run_dir / "run.json").read_text())
    assert run_json["status"] == "failed"
    assert run_json["summary"]["failed"] == 1
    assert run_json["rum"]["events_processed"] == 1


def test_unparseable_lines_are_counted_not_fatal(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    raw = (
        '{"type":"page.view","ts":"2026-06-02T12:00:00Z"}\n'
        "not json at all\n"
        "[1,2,3]\n"
        '{"type":"run.end","ts":"2026-06-02T12:00:01Z"}\n'
    )
    source = tmp_path / "rum.jsonl"
    source.write_text(raw, encoding="utf-8")
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert result.events_processed == 2
    assert result.parse_errors == 2


def test_missing_source_raises(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    with pytest.raises(RumIngestError):
        ingest_jsonl(tmp_path / "nope.jsonl", runs_root=runs_root, now=fixed_now)


def test_empty_input_raises(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = tmp_path / "rum.jsonl"
    source.write_text("", encoding="utf-8")
    with pytest.raises(RumIngestError):
        ingest_jsonl(source, runs_root=runs_root, now=fixed_now)


def test_run_id_is_deterministic_for_same_input(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-02T12:00:00Z",
                "route": "/x",
            },
        ],
    )
    first = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    second = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert first.run_id == second.run_id
