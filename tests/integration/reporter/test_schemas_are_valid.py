"""Every committed `*.schema.json` is itself a valid JSON Schema.

Task 03.08 final-tier guard: a malformed schema would silently break
runtime validation in CI without these checks. We:

1. Load each schema file under `packages/shared-schema/`.
2. Verify it's syntactically valid JSON.
3. Compile it with `jsonschema.Validator.check_schema(...)` so the
   *meta-schema* itself signs off on the structure.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCHEMA_ROOT = REPO_ROOT / "packages" / "shared-schema"


def _phase03_schemas() -> list[Path]:
    """Top-level Phase 03 wire schemas (run/findings/score)."""

    return sorted(SHARED_SCHEMA_ROOT.glob("*.schema.json"))


def _vendored_external_schemas() -> list[Path]:
    """Externally vendored schemas (SARIF — large, draft-04)."""

    return sorted(SHARED_SCHEMA_ROOT.joinpath("external").glob("*.json"))


def _domain_schemas() -> list[Path]:
    """Generated per-domain schemas."""

    return sorted(SHARED_SCHEMA_ROOT.joinpath("schemas").glob("*.schema.json"))


@pytest.mark.parametrize(
    "schema_path",
    _phase03_schemas() + _domain_schemas(),
    ids=lambda p: p.relative_to(SHARED_SCHEMA_ROOT).as_posix(),
)
def test_schema_is_valid_against_metaschema(schema_path: Path) -> None:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    # Use the validator class advertised by the schema's $schema (or
    # fall back to the auto-detected validator if absent).
    validator_cls = jsonschema.validators.validator_for(payload)
    validator_cls.check_schema(payload)


@pytest.mark.parametrize(
    "schema_path",
    _vendored_external_schemas(),
    ids=lambda p: p.relative_to(SHARED_SCHEMA_ROOT).as_posix(),
)
def test_external_schema_is_valid(schema_path: Path) -> None:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = jsonschema.validators.validator_for(payload)
    validator_cls.check_schema(payload)
