# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the RUM hosted ingest endpoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.rum import RumServerApp, handle_request


def _post(app: RumServerApp, body: bytes) -> tuple[int, dict[str, object]]:
    response = handle_request(app, "POST", "/rum", body)
    payload = json.loads(response.body) if response.body else {}
    return response.status, payload


@pytest.fixture
def app(tmp_path: Path) -> RumServerApp:
    return RumServerApp(runs_root=tmp_path / "runs", bake_threshold=3)


def test_healthz_returns_ok(app: RumServerApp) -> None:
    response = handle_request(app, "GET", "/healthz", b"")
    assert response.status == 200
    assert json.loads(response.body)["status"] == "ok"


def test_options_preflight_returns_204(app: RumServerApp) -> None:
    response = handle_request(app, "OPTIONS", "/rum", b"")
    assert response.status == 204
    headers = dict(response.headers)
    assert headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"


def test_post_rum_appends_to_inbox(app: RumServerApp) -> None:
    body = (
        json.dumps(
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": 1,
                "ts": "2026-06-03T12:00:00Z",
                "session_id": "alice",
                "route": "/home",
            }
        )
    ).encode("utf-8")
    status, payload = _post(app, body)
    assert status == 202
    assert payload["received"] == 1
    assert "baked_run_id" not in payload
    assert app.inbox_file.is_file()


def test_post_rum_drops_invalid_lines(app: RumServerApp) -> None:
    body = b'{"type":"page.view","ts":"x"}\nnot json\n[1,2,3]\n'
    status, payload = _post(app, body)
    assert status == 202
    assert payload["received"] == 1


def test_post_rum_bakes_when_threshold_reached(app: RumServerApp) -> None:
    lines = [
        json.dumps(
            {
                "schema_version": "1",
                "type": "page.view",
                "seq": i,
                "ts": f"2026-06-03T12:00:0{i}Z",
                "session_id": f"u{i}",
                "route": f"/r{i}",
            }
        )
        for i in range(3)
    ]
    body = "\n".join(lines).encode("utf-8")
    status, payload = _post(app, body)
    assert status == 202
    assert payload.get("baked_run_id")
    assert payload["sessions"] == 3
    # After baking, the inbox file is removed.
    assert not app.inbox_file.is_file()


def test_post_bake_endpoint_returns_when_empty(app: RumServerApp) -> None:
    response = handle_request(app, "POST", "/bake", b"")
    assert response.status == 200
    assert json.loads(response.body) == {"baked": False}


def test_post_bake_after_appending_returns_run_id(app: RumServerApp) -> None:
    body = json.dumps(
        {
            "schema_version": "1",
            "type": "page.view",
            "seq": 1,
            "ts": "2026-06-03T12:00:00Z",
        }
    ).encode("utf-8")
    _post(app, body)
    response = handle_request(app, "POST", "/bake", b"")
    payload = json.loads(response.body)
    assert payload["baked"] is True
    assert payload["events_processed"] == 1
    assert "run_id" in payload


def test_unknown_path_returns_404(app: RumServerApp) -> None:
    response = handle_request(app, "GET", "/missing", b"")
    assert response.status == 404


def test_method_not_allowed(app: RumServerApp) -> None:
    response = handle_request(app, "DELETE", "/rum", b"")
    assert response.status == 405


def test_on_bake_callback_fires(tmp_path: Path) -> None:
    captured: list[str] = []
    app = RumServerApp(
        runs_root=tmp_path / "runs",
        bake_threshold=1,
        on_bake=lambda result: captured.append(result.run_id),
    )
    body = json.dumps(
        {
            "schema_version": "1",
            "type": "page.view",
            "seq": 1,
            "ts": "2026-06-03T12:00:00Z",
        }
    ).encode("utf-8")
    _post(app, body)
    assert len(captured) == 1
    assert captured[0].startswith("RUN-")
