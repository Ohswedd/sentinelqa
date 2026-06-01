# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Integration tests for the ``sentinel ask`` CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sentinel_cli.app import build_app


def _write_run(path: Path, *, run_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "passed",
                "quality_score": 88.0,
                "modules_run": ["security"],
                "target": {"base_url": "https://app.example.com", "host": "app.example.com"},
                "started_at": "2026-06-01T00:00:00+00:00",
                "finished_at": "2026-06-01T00:01:00+00:00",
                "summary": {"passed": 5, "failed": 0, "blocked": 0, "info": 1},
            }
        ),
        encoding="utf-8",
    )
    (path / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
    (path / "score.json").write_text("{}", encoding="utf-8")


def test_ask_with_explicit_run_id_returns_deterministic_answer(tmp_path: Path) -> None:
    artifacts = tmp_path / "runs"
    run_dir = artifacts / "RUN-XAAAAAAAAAAA"
    _write_run(run_dir, run_id="RUN-XAAAAAAAAAAA")

    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(
        app,
        [
            "ask",
            "Why did the score drop?",
            "--run-id",
            "RUN-XAAAAAAAAAAA",
            "--output",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "RUN-XAAAAAAAAAAA" in result.stdout
    assert "88.0" in result.stdout or "88" in result.stdout


def test_ask_json_mode_emits_structured_payload(tmp_path: Path) -> None:
    artifacts = tmp_path / "runs"
    run_dir = artifacts / "RUN-XAAAAAAAAAAA"
    _write_run(run_dir, run_id="RUN-XAAAAAAAAAAA")

    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(
        app,
        [
            "--json",
            "ask",
            "Why?",
            "--run-id",
            "RUN-XAAAAAAAAAAA",
            "--output",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "ask"
    assert payload["run_id"] == "RUN-XAAAAAAAAAAA"
    assert payload["provider"] == "deterministic"


def test_ask_quiet_mode_emits_text_only(tmp_path: Path) -> None:
    artifacts = tmp_path / "runs"
    run_dir = artifacts / "RUN-XAAAAAAAAAAA"
    _write_run(run_dir, run_id="RUN-XAAAAAAAAAAA")

    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(
        app,
        [
            "--quiet",
            "ask",
            "What?",
            "--run-id",
            "RUN-XAAAAAAAAAAA",
            "--output",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip()
    assert "[provider:" not in result.stdout


def test_ask_returns_error_when_run_missing(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    app = build_app()
    result = runner.invoke(
        app,
        [
            "ask",
            "Why?",
            "--run-id",
            "RUN-NOSUCHRUNXX",
            "--output",
            str(tmp_path / "runs"),
        ],
    )
    assert result.exit_code == 2
