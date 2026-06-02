# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the RUM replay view."""

from __future__ import annotations

import json
from pathlib import Path

from engine.reporter.serve.rum_replay import (
    build_replay_payload,
    render_replay_html,
)


def _write_run(
    runs_root: Path,
    *,
    run_id: str,
    sessions: list[dict[str, object]],
    events: list[dict[str, object]],
) -> Path:
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "sessions.json").write_text(
        json.dumps({"schema_version": "1", "count": len(sessions), "sessions": sessions}),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )
    return run_dir


def test_returns_none_for_unknown_run(tmp_path: Path) -> None:
    assert build_replay_payload(tmp_path, "RUN-MISSING") is None


def test_returns_none_when_sessions_artifact_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "RUN-X"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")
    assert build_replay_payload(tmp_path, "RUN-X") is None


def test_builds_payload(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        run_id="RUN-AAAAAAAAAAAA",
        sessions=[
            {
                "session_id": "alice",
                "event_count": 2,
                "page_views": 1,
                "errors": 1,
                "started_at": "2026-06-03T12:00:00Z",
                "ended_at": "2026-06-03T12:00:05Z",
            },
        ],
        events=[
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
                "type": "page.error",
                "seq": 2,
                "ts": "2026-06-03T12:00:05Z",
                "session_id": "alice",
                "message": "boom",
            },
        ],
    )
    payload = build_replay_payload(tmp_path, "RUN-AAAAAAAAAAAA")
    assert payload is not None
    assert payload["total_events"] == 2
    assert len(payload["events_by_session"]["alice"]) == 2


def test_render_replay_html_escapes_event_values(tmp_path: Path) -> None:
    payload = {
        "run_id": "RUN-AAAAAAAAAAAA",
        "sessions": [
            {
                "session_id": "<script>",
                "event_count": 1,
                "page_views": 1,
                "errors": 0,
                "started_at": "x",
                "ended_at": "x",
            },
        ],
        "events_by_session": {
            "<script>": [
                {
                    "schema_version": "1",
                    "type": "page.view",
                    "seq": 1,
                    "ts": "x",
                    "session_id": "<script>",
                    "route": "<script>alert('xss')</script>",
                }
            ]
        },
        "total_events": 1,
    }
    html = render_replay_html("RUN-AAAAAAAAAAAA", payload)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_replay_html_handles_empty(tmp_path: Path) -> None:
    payload = {
        "run_id": "RUN-AAAAAAAAAAAA",
        "sessions": [],
        "events_by_session": {},
        "total_events": 0,
    }
    html = render_replay_html("RUN-AAAAAAAAAAAA", payload)
    assert "No sessions" in html


def test_router_serves_html(tmp_path: Path) -> None:
    from engine.reporter.serve import ViewerApp, handle_request

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_run(
        runs_root,
        run_id="RUN-BBBBBBBBBBBB",
        sessions=[
            {
                "session_id": "u1",
                "event_count": 1,
                "page_views": 1,
                "errors": 0,
                "started_at": "x",
                "ended_at": "x",
            }
        ],
        events=[
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "x",
                "session_id": "u1",
                "route": "/x",
            }
        ],
    )
    app = ViewerApp(runs_root=runs_root)
    response = handle_request(app, "GET", "/runs/RUN-BBBBBBBBBBBB/rum")
    assert response.status == 200
    assert b"RUM replay" in response.body


def test_router_returns_404_when_no_rum_data(tmp_path: Path) -> None:
    from engine.reporter.serve import ViewerApp, handle_request

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    (runs_root / "RUN-X").mkdir()
    app = ViewerApp(runs_root=runs_root)
    response = handle_request(app, "GET", "/runs/RUN-X/rum")
    assert response.status == 404


def test_router_serves_json(tmp_path: Path) -> None:
    from engine.reporter.serve import ViewerApp, handle_request

    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    _write_run(
        runs_root,
        run_id="RUN-CCCCCCCCCCCC",
        sessions=[
            {
                "session_id": "u1",
                "event_count": 1,
                "page_views": 1,
                "errors": 0,
                "started_at": "x",
                "ended_at": "x",
            }
        ],
        events=[
            {"schema_version": "1", "type": "page.view", "seq": 1, "ts": "x", "session_id": "u1"}
        ],
    )
    app = ViewerApp(runs_root=runs_root)
    response = handle_request(app, "GET", "/api/runs/RUN-CCCCCCCCCCCC/rum.json")
    assert response.status == 200
    payload = json.loads(response.body)
    assert payload["total_events"] == 1
