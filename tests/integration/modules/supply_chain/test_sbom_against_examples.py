"""Integration tests for :mod:`modules.supply_chain.sbom` (Phase 33.01).

Run the SBOM generator against synthetic project trees that mimic the
Phase 26 example apps' lockfile shapes, then validate every emitted
CycloneDX document against the vendored schema
(``packages/shared-schema/external/cyclonedx-1.5.json``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

from modules.supply_chain.sbom import CYCLONEDX_SPEC_VERSION, build_sbom

REPO_ROOT = Path(__file__).resolve().parents[4]
CYCLONEDX_SCHEMA = json.loads(
    (REPO_ROOT / "packages" / "shared-schema" / "external" / "cyclonedx-1.5.json").read_text(
        encoding="utf-8"
    )
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_build_sbom_emits_valid_cyclonedx_for_python_project(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests==2.31.0\nflask==3.0.0\n")
    sbom = build_sbom(
        project_root=tmp_path,
        project_name="example-flask",
        sbom_dir=tmp_path / "sbom",
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert sbom.components_count == 2
    output = json.loads(
        (tmp_path / "sbom" / "requirements.txt.cdx.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(output, CYCLONEDX_SCHEMA)
    assert output["specVersion"] == CYCLONEDX_SPEC_VERSION
    assert output["bomFormat"] == "CycloneDX"
    assert output["serialNumber"].startswith("urn:uuid:")
    assert {c["name"] for c in output["components"]} == {"requests", "flask"}


def test_build_sbom_handles_multiple_lockfiles(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests==2.31.0\n")
    payload = {
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "root"},
            "node_modules/lodash": {"version": "4.17.21", "license": "MIT"},
        },
    }
    _write(tmp_path / "package-lock.json", json.dumps(payload))
    sbom = build_sbom(
        project_root=tmp_path,
        project_name="hybrid",
        sbom_dir=tmp_path / "sbom",
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert {lf.kind for lf in sbom.lockfiles} == {"requirements.txt", "package-lock.json"}
    assert sbom.components_count == 2  # requests + lodash, deduplicated.
    for output_filename in ("requirements.txt.cdx.json", "package-lock.json.cdx.json"):
        output = json.loads((tmp_path / "sbom" / output_filename).read_text(encoding="utf-8"))
        jsonschema.validate(output, CYCLONEDX_SCHEMA)


def test_build_sbom_is_byte_stable_for_same_inputs(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "flask==3.0.0\n")
    timestamp = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    first = build_sbom(
        project_root=tmp_path,
        project_name="determinism",
        sbom_dir=tmp_path / "sbom-1",
        now=timestamp,
    )
    second = build_sbom(
        project_root=tmp_path,
        project_name="determinism",
        sbom_dir=tmp_path / "sbom-2",
        now=timestamp,
    )
    first_payload = (tmp_path / "sbom-1" / "requirements.txt.cdx.json").read_bytes()
    second_payload = (tmp_path / "sbom-2" / "requirements.txt.cdx.json").read_bytes()
    assert first_payload == second_payload
    assert first.components_count == second.components_count


def test_build_sbom_records_parser_errors_without_raising(tmp_path: Path) -> None:
    _write(tmp_path / "uv.lock", "not valid toml [[[")
    sbom = build_sbom(
        project_root=tmp_path,
        project_name="bad-lockfile",
        sbom_dir=tmp_path / "sbom",
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert sbom.lockfiles[0].parse_error is not None
    assert sbom.components_count == 0
    assert sbom.lockfiles[0].cyclonedx_path is None


def test_build_sbom_index_written(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests==2.31.0\n")
    build_sbom(
        project_root=tmp_path,
        project_name="indexed",
        sbom_dir=tmp_path / "sbom",
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    payload = json.loads((tmp_path / "sbom" / "index.json").read_text(encoding="utf-8"))
    assert payload["project_name"] == "indexed"
    assert payload["schema_version"] == "1"
