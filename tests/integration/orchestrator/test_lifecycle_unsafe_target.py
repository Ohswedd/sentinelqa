"""Unsafe target → exit code 4 + minimal artifact tree."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.run_lifecycle import RunLifecycle


def test_unsafe_target_marks_run_blocked(tmp_path: Path) -> None:
    config_path = tmp_path / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: bad-app\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: []\n",
        encoding="utf-8",
    )
    config = load_config(config_path)

    artifacts_root = tmp_path / ".sentinel" / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(config)

    assert test_run.status == "unsafe_blocked"
    run_dir = artifacts_root / test_run.id
    assert (run_dir / "audit.log").exists()
    audit_lines = (run_dir / "audit.log").read_text(encoding="utf-8").strip().splitlines()
    assert audit_lines
    last = json.loads(audit_lines[-1])
    assert last["event"] == "safety_block"
    # run.json is written with the unsafe_blocked status.
    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "unsafe_blocked"
