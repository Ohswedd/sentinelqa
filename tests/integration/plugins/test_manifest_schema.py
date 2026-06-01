"""Drift guard: ``plugin-manifest.schema.json`` mirrors the Pydantic model.

The schema file at ``packages/shared-schema/plugin-manifest.schema.json``
is the wire format plugin authors publish. The Pydantic model
:class:`engine.plugins.manifest.Manifest` is the runtime equivalent.
They MUST agree — drift would silently let a manifest validate one
way and fail the other.

This test:

1. Loads the JSON Schema.
2. Compiles it through jsonschema's meta-schema check.
3. Round-trips a small fixture set: every payload Pydantic accepts
 must also pass the JSON Schema, and every payload Pydantic
 rejects must also fail the JSON Schema (best-effort: some
 semantic rules — like the duplicate-name guard — are Pydantic-only;
 those are documented inline).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from engine.plugins import load_manifest_dict
from engine.plugins.errors import PluginManifestError

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "packages" / "shared-schema" / "plugin-manifest.schema.json"


def _load_schema() -> dict[str, object]:
    data: dict[str, object] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return data


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists()


def test_schema_passes_meta_schema_check() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


# ---------------------------------------------------------------------------
# Round-trip: accepted-by-both
# ---------------------------------------------------------------------------


VALID_PAYLOADS: list[dict] = [
    {
        "name": "tiny",
        "version": "0.1.0",
        "kind": "scanner",
        "capabilities": ["audit"],
        "permissions": ["fs.read"],
        "requires_protocol": ">=1.0,<2.0",
    },
    {
        "name": "tiny-2",
        "version": "1.2.3-rc.1",
        "kind": "reporter",
        "capabilities": [],
        "permissions": [],
        "requires_protocol": "==1.0.0",
    },
    {
        "name": "auth-helper",
        "version": "0.0.1",
        "kind": "auth",
        "capabilities": ["sso_login"],
        "permissions": ["network.outbound", "env.read:DATABASE_URL"],
        "requires_protocol": ">=1.0",
        "description": "Acquires OAuth tokens for staging.",
    },
]


@pytest.mark.parametrize("payload", VALID_PAYLOADS)
def test_valid_payload_passes_jsonschema(payload: dict) -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize("payload", VALID_PAYLOADS)
def test_valid_payload_passes_pydantic(payload: dict) -> None:
    load_manifest_dict(payload)


# ---------------------------------------------------------------------------
# Drift: rejected-by-both
# ---------------------------------------------------------------------------


INVALID_PAYLOADS: list[dict] = [
    {  # missing required field
        "name": "tiny",
        "version": "0.1.0",
        "kind": "scanner",
    },
    {  # bad name pattern (uppercase + space)
        "name": "Bad Name",
        "version": "0.1.0",
        "kind": "scanner",
        "requires_protocol": ">=1.0",
    },
    {  # bad version
        "name": "tiny",
        "version": "v1",
        "kind": "scanner",
        "requires_protocol": ">=1.0",
    },
    {  # unknown kind
        "name": "tiny",
        "version": "0.1.0",
        "kind": "weirdo",
        "requires_protocol": ">=1.0",
    },
    {  # bad permission grammar
        "name": "tiny",
        "version": "0.1.0",
        "kind": "scanner",
        "permissions": ["UPPERCASE"],
        "requires_protocol": ">=1.0",
    },
    {  # additionalProperties forbidden
        "name": "tiny",
        "version": "0.1.0",
        "kind": "scanner",
        "requires_protocol": ">=1.0",
        "extra": "boom",
    },
]


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_payload_fails_jsonschema(payload: dict) -> None:
    schema = _load_schema()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_payload_fails_pydantic(payload: dict) -> None:
    with pytest.raises(PluginManifestError):
        load_manifest_dict(payload)


def test_pydantic_rejects_fs_write_outside_runs() -> None:
    # Pydantic enforces the allow-list at the permission-grammar layer
    # (the JSON Schema only enforces the grammar pattern, not the allow
    # list — that's a layered defence). Documented here so future
    # readers don't mistake it for drift.
    with pytest.raises(PluginManifestError):
        load_manifest_dict(
            {
                "name": "tiny",
                "version": "0.1.0",
                "kind": "scanner",
                "permissions": ["fs.write:/etc"],
                "requires_protocol": ">=1.0",
            }
        )
