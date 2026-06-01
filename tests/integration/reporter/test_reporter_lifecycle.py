"""Reporter is wired into the run lifecycle.

Drives the full :class:`RunLifecycle` and verifies the
``generate_reports`` step produces the formats configured in
``config.report.formats``.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle


def _write_config(root: Path, *, formats: tuple[str, ...]) -> Path:
    config_path = root / "sentinel.config.yaml"
    formats_yaml = "\n".join(f"    - {f}" for f in formats)
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: test-app\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n"
        "report:\n"
        "  formats:\n"
        f"{formats_yaml}\n",
        encoding="utf-8",
    )
    return config_path


def test_lifecycle_emits_markdown_when_configured(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, formats=("markdown", "junit"))
    config = load_config(config_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    registry = ModuleRegistry()
    registry.register_module("functional", lambda cfg, decision: {"ok": True})

    lifecycle = RunLifecycle(artifacts_root=artifacts_root, registry=registry)
    test_run = lifecycle.execute(config)

    run_dir = artifacts_root / test_run.id
    assert (run_dir / "report.md").exists(), "Reporter should have written report.md"
    assert (run_dir / "junit.xml").exists(), "Reporter should have written junit.xml"
    # SARIF was not requested → no file.
    assert not (run_dir / "sarif.json").exists()
    # audit.log should record the artifact_emitted events.
    audit_lines = (run_dir / "audit.log").read_text(encoding="utf-8").splitlines()
    artifact_events = [
        json.loads(line)
        for line in audit_lines
        if line and json.loads(line).get("event") == "artifact_emitted"
    ]
    formats_seen = {e["format"] for e in artifact_events}
    assert {"markdown", "junit", "run"} <= formats_seen


def test_lifecycle_emits_json_alias_trio(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, formats=("json",))
    config = load_config(config_path)
    artifacts_root = tmp_path / ".sentinel" / "runs"
    registry = ModuleRegistry()
    registry.register_module("functional", lambda cfg, decision: {"ok": True})

    lifecycle = RunLifecycle(artifacts_root=artifacts_root, registry=registry)
    test_run = lifecycle.execute(config)

    run_dir = artifacts_root / test_run.id
    # `json` alias should expand to run.json + score.json (findings.json
    # is skipped because the lifecycle hasn't surfaced findings yet).
    assert (run_dir / "run.json").exists()
    assert (run_dir / "score.json").exists()
    score_payload = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    assert score_payload["schema_version"] == "1"
    # run.json from the Reporter should overwrite the legacy run.json
    # written by persist_artifacts. The new shape has artifact_paths.
    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert "artifact_paths" in run_payload
    assert run_payload["artifact_paths"]["score"] == "score.json"
