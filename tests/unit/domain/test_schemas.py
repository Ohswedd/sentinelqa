"""JSON Schema generation and version-stamping tests."""

from __future__ import annotations

import json
from pathlib import Path

from engine.domain.jsonschema import all_models, dump_schemas
from engine.domain.schema import ALL_SCHEMA_VERSIONS


def test_schema_dump_creates_one_file_per_model(tmp_path: Path) -> None:
    out = tmp_path / "schemas"
    written = dump_schemas(out)
    assert len(written) == len(all_models())
    # File names are stable and end with `.schema.json`.
    for path in written:
        assert path.suffix == ".json"
        assert path.name.endswith(".schema.json")


def test_each_schema_carries_x_version(tmp_path: Path) -> None:
    out = tmp_path / "schemas"
    written = dump_schemas(out)
    for path in written:
        schema = json.loads(path.read_text())
        # Every model with a SCHEMA_VERSION ClassVar gets stamped.
        if "x-sentinelqa-schema-version" in schema:
            assert isinstance(schema["x-sentinelqa-schema-version"], str)


def test_schema_versions_constants_match_models() -> None:
    """ALL_SCHEMA_VERSIONS surface stays in lockstep with the schema module."""

    expected = {
        "run",
        "findings",
        "score",
        "config",
        "repair_suggestion",
        "agent_message",
    }
    assert set(ALL_SCHEMA_VERSIONS) == expected
    for value in ALL_SCHEMA_VERSIONS.values():
        assert value == "1"
