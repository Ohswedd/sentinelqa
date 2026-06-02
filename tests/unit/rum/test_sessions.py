# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for RUM session correlation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.rum import ingest_jsonl


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def test_events_group_by_session_id(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "session_id": "alice",
                "route": "/home",
            },
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 2,
                "ts": "2026-06-03T12:00:05Z",
                "session_id": "bob",
                "route": "/home",
            },
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 3,
                "ts": "2026-06-03T12:00:10Z",
                "session_id": "alice",
                "route": "/checkout",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert len(result.sessions) == 2
    by_id = {s.session_id: s for s in result.sessions}
    assert by_id["alice"].event_count == 2
    assert by_id["alice"].page_views == 2
    assert by_id["bob"].event_count == 1


def test_events_without_session_id_bucket_under_anonymous(
    tmp_path: Path, fixed_now: datetime
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "route": "/a",
            },
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 2,
                "ts": "2026-06-03T12:00:10Z",
                "route": "/b",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert len(result.sessions) == 1
    assert result.sessions[0].session_id == "anonymous"
    assert result.sessions[0].event_count == 2


def test_session_errors_count_page_errors(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "session_id": "alice",
            },
            {
                "schema_version": "1",
                "type": "page.error",
                "seq": 2,
                "ts": "2026-06-03T12:00:01Z",
                "session_id": "alice",
                "route": "/checkout",
                "message": "kaboom",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    assert result.sessions[0].errors == 1
    assert result.sessions[0].page_views == 1


def test_sessions_json_artifact_is_written(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "session_id": "u1",
                "route": "/x",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    payload = json.loads((result.run_dir / "sessions.json").read_text())
    assert payload["count"] == 1
    assert payload["sessions"][0]["session_id"] == "u1"


def test_run_json_carries_session_summary(tmp_path: Path, fixed_now: datetime) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    source = _write_jsonl(
        tmp_path / "rum.jsonl",
        [
            {
                "schema_version": "1",
                "type": "page.error",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "session_id": "u1",
                "route": "/x",
                "message": "boom",
            },
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 2,
                "ts": "2026-06-03T12:00:01Z",
                "session_id": "u2",
                "route": "/y",
            },
        ],
    )
    result = ingest_jsonl(source, runs_root=runs_root, now=fixed_now)
    run_json = json.loads((result.run_dir / "run.json").read_text())
    assert run_json["rum"]["session_count"] == 2
    assert run_json["rum"]["sessions_with_errors"] == 1
