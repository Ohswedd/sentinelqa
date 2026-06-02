# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the stdlib viewer app (router-level)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.reporter.serve import ViewerApp, handle_request, render_index_html


def _write_run(
    parent: Path,
    *,
    run_id: str,
    started_at: str = "2026-06-01T00:00:00+00:00",
    quality: float | None = 90.0,
    findings: list[dict] | None = None,
) -> Path:
    run_dir = parent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "run_id": run_id,
        "status": "passed",
        "modules_run": ["security"],
        "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
        "started_at": started_at,
        "finished_at": started_at,
        "summary": {"passed": 1, "failed": 0, "blocked": 0, "info": 0},
    }
    if quality is not None:
        payload["quality_score"] = quality
    (run_dir / "run.json").write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "findings.json").write_text(
        json.dumps({"findings": findings or []}), encoding="utf-8"
    )
    (run_dir / "score.json").write_text("{}", encoding="utf-8")
    (run_dir / "report.html").write_text(
        "<!doctype html><html><body>ok</body></html>", encoding="utf-8"
    )
    return run_dir


def test_index_lists_runs(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/")
    assert response.status == 200
    assert b"RUN-XAAAAAAAAAAA" in response.body
    assert b"text/html" in dict(response.headers)["Content-Type"].encode()


def test_index_handles_empty_runs_root(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/")
    assert response.status == 200
    assert b"No runs yet" in response.body


def test_healthz_returns_ok(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/healthz")
    assert response.status == 200
    assert response.body == b"ok"


def test_widget_js_is_served(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/widget.js")
    assert response.status == 200
    assert b"fetch" in response.body


def test_api_runs_json_returns_window(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/api/runs.json")
    assert response.status == 200
    payload = json.loads(response.body)
    assert payload["runs"][0]["run_id"] == "RUN-XAAAAAAAAAAA"


def test_api_trends_json_has_score_and_severity_series(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", findings=[{"id": "F", "severity": "high"}])
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/api/trends.json")
    payload = json.loads(response.body)
    assert payload["score"][0]["y"] == 90.0
    assert payload["severity"]["high"][0]["y"] == 1


def test_api_status_json_returns_pass_above_threshold(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA", quality=92.0)
    app = ViewerApp(runs_root=tmp_path, threshold=80.0)
    response = handle_request(app, "GET", "/api/status.json")
    payload = json.loads(response.body)
    assert payload["release_decision"] == "pass"


def test_api_status_json_handles_no_runs(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/api/status.json")
    payload = json.loads(response.body)
    assert payload["status"] == "no-runs"
    assert payload["release_decision"] == "inconclusive"


def test_api_diff_returns_404_for_unknown_runs(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(
        app,
        "GET",
        "/api/diff/RUN-XAAAAAAAAAAA/RUN-YBBBBBBBBBBB.json",
    )
    assert response.status == 404


def test_api_diff_returns_400_for_bad_run_id(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/api/diff/notvalid/RUN-XYZ.json")
    assert response.status == 400


def test_api_diff_returns_payload_for_known_runs(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-BEFOREAAAAA")
    _write_run(tmp_path, run_id="RUN-AFTERRAAAAA")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(
        app,
        "GET",
        "/api/diff/RUN-BEFOREAAAAA/RUN-AFTERRAAAAA.json",
    )
    assert response.status == 200
    payload = json.loads(response.body)
    assert payload["before_run_id"] == "RUN-BEFOREAAAAA"
    assert payload["after_run_id"] == "RUN-AFTERRAAAAA"


def test_run_artifact_served(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/runs/RUN-XAAAAAAAAAAA/report.html")
    assert response.status == 200
    assert b"<!doctype html>" in response.body
    assert "text/html" in dict(response.headers)["Content-Type"]


def test_run_artifact_404_for_missing(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/runs/RUN-XAAAAAAAAAAA/missing.html")
    assert response.status == 404


def test_run_artifact_400_for_bad_filename(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/runs/RUN-XAAAAAAAAAAA/../etc/passwd")
    assert response.status == 400 or response.status == 404


def test_method_not_allowed_for_post(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "POST", "/")
    assert response.status == 405


def test_404_for_unknown_path(tmp_path: Path) -> None:
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/api/nonexistent")
    assert response.status == 404


def test_render_index_html_escapes_runs_root(tmp_path: Path) -> None:
    weird = tmp_path / "<x>"
    weird.mkdir()
    app = ViewerApp(runs_root=weird)
    html = render_index_html(app)
    assert "<x>" not in html.split("<title>")[1]


def test_run_artifact_blocks_unsupported_extension(tmp_path: Path) -> None:
    _write_run(tmp_path, run_id="RUN-XAAAAAAAAAAA")
    weird = tmp_path / "RUN-XAAAAAAAAAAA" / "evil.exe"
    weird.write_bytes(b"MZ\x90\x00")
    app = ViewerApp(runs_root=tmp_path)
    response = handle_request(app, "GET", "/runs/RUN-XAAAAAAAAAAA/evil.exe")
    assert response.status == 415
