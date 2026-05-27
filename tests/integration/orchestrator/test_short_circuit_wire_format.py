"""Short-circuit lifecycle exits use the same `run.json` wire format
as the happy path (gap #2 resolution).

Both `_finalize_unsafe` and `_finalize_dry_run` now route through
`engine.reporter.run_writer.write_run`, so every run — passed, failed,
unsafe_blocked, dry_run, incomplete — is described by the same versioned
schema (`packages/shared-schema/run.schema.json`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from engine.config.loader import load_config
from engine.orchestrator.run_lifecycle import RunLifecycle

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "run.schema.json"


@pytest.fixture(scope="module")
def run_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return payload


def _unsafe_config(tmp_path: Path) -> Path:
    p = tmp_path / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n"
        "  name: bad-app\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: []\n",
        encoding="utf-8",
    )
    return p


def _local_config(tmp_path: Path) -> Path:
    p = tmp_path / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n"
        "  name: dry\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    return p


def test_unsafe_run_json_uses_wire_format(tmp_path: Path, run_schema: dict[str, Any]) -> None:
    config = load_config(_unsafe_config(tmp_path))
    artifacts_root = tmp_path / ".sentinel" / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(config)
    payload = json.loads((artifacts_root / test_run.id / "run.json").read_text(encoding="utf-8"))

    # Schema-valid + new shape (artifact_paths, summary, etc.).
    jsonschema.validate(payload, run_schema)
    assert payload["schema_version"] == "1"
    assert payload["status"] == "unsafe_blocked"
    assert payload["release_decision"] == "unsafe_target_rejected"
    assert payload["quality_score"] is None
    assert payload["artifact_paths"]["audit_log"] == "audit.log"
    assert payload["artifact_paths"]["findings"] is None
    # Safety-block message lands in the redacted errors[] array.
    assert payload["errors"]
    assert payload["errors"][0]["code"] == "E-SAFE-001"


def test_dry_run_run_json_uses_wire_format(tmp_path: Path, run_schema: dict[str, Any]) -> None:
    config = load_config(_local_config(tmp_path))
    artifacts_root = tmp_path / ".sentinel" / "runs"
    lifecycle = RunLifecycle(artifacts_root=artifacts_root)
    test_run = lifecycle.execute(config, dry_run=True)
    payload = json.loads((artifacts_root / test_run.id / "run.json").read_text(encoding="utf-8"))

    jsonschema.validate(payload, run_schema)
    assert payload["schema_version"] == "1"
    assert payload["status"] == "dry_run"
    assert payload["release_decision"] == "inconclusive"
    assert payload["quality_score"] is None
    assert payload["artifact_paths"]["audit_log"] == "audit.log"
    assert "config_digest" in payload
    assert payload["config_digest"].startswith("sha256:")
