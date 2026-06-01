"""API-snapshot gate (ADR-0021, task 16.06).

CI fails if the live public surface diverges from
``packages/python-sdk/api-snapshot.json``. Regenerate via
``make sdk-api-snapshot`` and ship the diff with an ADR per
``packages/python-sdk/__deprecation_policy.md``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = REPO_ROOT / "packages" / "python-sdk" / "api-snapshot.json"
DUMPER_PATH = REPO_ROOT / "scripts" / "dump-sdk-api-snapshot.py"


def _live_snapshot() -> object:
    # Spawn the dumper in a subprocess so it picks up the live tree
    # exactly the way CI does.
    output = subprocess.check_output(
        [sys.executable, str(DUMPER_PATH)],
        cwd=str(REPO_ROOT),
    )
    assert output  # script prints the destination path
    payload: object = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return payload


def test_snapshot_file_exists() -> None:
    assert (
        SNAPSHOT_PATH.exists()
    ), f"missing {SNAPSHOT_PATH}. Run `make sdk-api-snapshot` to create it."


def test_snapshot_has_schema_version() -> None:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == "1"
    assert "modules" in payload


def test_snapshot_lists_public_modules() -> None:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    modules = set(payload["modules"].keys())
    assert modules == {
        "sentinelqa",
        "sentinelqa.errors",
        "sentinelqa.agent",
        "sentinelqa.plugins",
    }


def test_snapshot_matches_live_surface(tmp_path: Path) -> None:
    # Snapshot file content matches the live dump (drift gate).
    committed = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    # Generate to a temp location to avoid mutating the committed file
    # if the test fails mid-run.
    backup = SNAPSHOT_PATH.read_text(encoding="utf-8")
    try:
        live = _live_snapshot()
    finally:
        SNAPSHOT_PATH.write_text(backup, encoding="utf-8")
    assert committed == live, (
        "Public SDK surface drifted. Run `make sdk-api-snapshot`, review "
        "the diff, and follow `packages/python-sdk/__deprecation_policy.md`."
    )


def test_snapshot_includes_prd_class_names() -> None:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    root = payload["modules"]["sentinelqa"]
    for name in (
        "Sentinel",
        "AuditResult",
        "Finding",
        "Evidence",
        "TestPlan",
        "Flow",
        "RiskMap",
        "QualityGate",
        "Policy",
        "ModuleResult",
        "RepairSuggestion",
    ):
        assert name in root, f"our product spec3 class {name} missing from snapshot"


def test_snapshot_includes_from_dict_in_errors_module() -> None:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    errors_mod = payload["modules"]["sentinelqa.errors"]
    assert "from_dict" in errors_mod
    assert errors_mod["from_dict"]["kind"] == "function"
