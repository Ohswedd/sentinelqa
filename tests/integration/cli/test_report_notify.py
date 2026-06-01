"""`sentinel report --notify slack` integration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.orchestrator.registry import LifecyclePhase, default_registry
from engine.orchestrator.run_lifecycle import RunLifecycle
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.unit.scoring.conftest import make_finding


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "report:\n  formats: [json, html, junit, sarif, markdown]\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def _seed_run(tmp_path: Path) -> tuple[Path, str]:
    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject(ctx: Any) -> None:
        ctx.typed_findings = (
            make_finding(
                id="FND-NOTIFYABCDEF",
                module="accessibility",
                severity="medium",
                run_id=ctx.run_id,
            ),
        )

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, inject)
    try:
        runs_root = tmp_path / ".sentinel" / "runs"
        lifecycle = RunLifecycle(artifacts_root=runs_root)
        test_run = lifecycle.execute(config)
    finally:
        registry.clear()
    return runs_root, test_run.id


def test_notify_slack_dispatches_with_webhook_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/a/b/c")
    captured: list[Mapping[str, Any]] = []

    def _stub_post_payload(
        *,
        payload: Mapping[str, Any],
        webhook_url: str,
        dedup_path: Path | None = None,
        **_: Any,
    ) -> str:
        captured.append({"payload": payload, "webhook": webhook_url})
        return "ok"

    monkeypatch.setattr("integrations.slack.post_payload", _stub_post_payload)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
            "--notify",
            "slack",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured, "expected post_payload to be called"
    assert captured[0]["webhook"] == "https://hooks.slack.com/services/a/b/c"
    assert "blocks" in captured[0]["payload"]


def test_notify_slack_missing_webhook_exits_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
            "--notify",
            "slack",
        ],
    )
    # exit 2 = config error.
    assert result.exit_code == 2
    assert "SLACK_WEBHOOK_URL" in result.stderr


def test_notify_unknown_channel_exits_config_error(
    tmp_path: Path,
) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
            "--notify",
            "discord",
        ],
    )
    assert result.exit_code == 2
    assert "not supported" in result.stderr.lower()


def test_notify_skipped_when_no_flag(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0


def test_notify_dispatch_in_json_mode_does_not_corrupt_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/a/b/c")
    monkeypatch.setattr("integrations.slack.post_payload", lambda **_: "ok")
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
            "--notify",
            "slack",
        ],
    )
    assert result.exit_code == 0
    # Stdout must remain a single JSON line.
    line = result.stdout.strip().splitlines()[-1]
    json.loads(line)  # raises if not JSON
