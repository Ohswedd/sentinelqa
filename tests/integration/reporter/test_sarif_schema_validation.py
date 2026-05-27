"""SARIF goldens validate against the vendored official schema (task 03.05)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SARIF_SCHEMA = REPO_ROOT / "packages" / "shared-schema" / "external" / "sarif-2.1.0.json"
GOLDENS_DIR = REPO_ROOT / "tests" / "golden" / "reports" / "sarif"


@pytest.fixture(scope="module")
def sarif_schema() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SARIF_SCHEMA.read_text(encoding="utf-8"))
    return payload


@pytest.mark.parametrize(
    "golden_name",
    [
        "sarif.empty.golden.json",
        "sarif.critical.golden.json",
        "sarif.mixed.golden.json",
    ],
)
def test_sarif_golden_validates_against_official_schema(
    sarif_schema: dict[str, Any],
    golden_name: str,
) -> None:
    golden_path = GOLDENS_DIR / golden_name
    if not golden_path.exists():
        pytest.skip(f"Golden {golden_name} not generated (run SENTINELQA_UPDATE_GOLDENS=1).")
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    # SARIF 2.1.0 schema is draft-04; use Draft4Validator explicitly.
    validator = jsonschema.Draft4Validator(sarif_schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert errors == [], "\n".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)
