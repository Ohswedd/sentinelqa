"""backward-compatibility diff + snapshot persistence."""

from __future__ import annotations

from pathlib import Path

from modules.api.backward_compat import (
    diff_snapshots,
    load_previous_snapshot,
    load_snapshot,
    write_snapshot,
)
from modules.api.models import (
    API_SCHEMA_SNAPSHOT_VERSION,
    ApiSchemaEndpoint,
    ApiSchemaSnapshot,
)


def _endpoint(
    method: str,
    path: str,
    *,
    required_response_fields: tuple[str, ...] = (),
    required_request_fields: tuple[str, ...] = (),
    response_field_types: tuple[tuple[str, str], ...] = (),
) -> ApiSchemaEndpoint:
    return ApiSchemaEndpoint(
        method=method,
        path=path,
        required_request_fields=required_request_fields,
        response_status_codes=(200,),
        required_response_fields=required_response_fields,
        response_field_types=response_field_types,
    )


def test_removed_endpoint_flags_high(tmp_path: Path) -> None:
    prev = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(_endpoint("GET", "/items"),),
    )
    cur = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(),
    )
    result = diff_snapshots(previous=prev, current=cur)
    assert result.check == "backward_compat"
    assert any(
        issue.rule_id == "COMPAT-REMOVED-ENDPOINT" and issue.severity == "high"
        for issue in result.issues
    )


def test_removed_required_response_field(tmp_path: Path) -> None:
    prev = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(
            _endpoint(
                "GET",
                "/items",
                required_response_fields=("200:id", "200:name"),
            ),
        ),
    )
    cur = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(
            _endpoint(
                "GET",
                "/items",
                required_response_fields=("200:id",),
            ),
        ),
    )
    result = diff_snapshots(previous=prev, current=cur)
    assert any(issue.rule_id == "COMPAT-REMOVED-REQUIRED-RESPONSE-FIELD" for issue in result.issues)


def test_added_required_request_field(tmp_path: Path) -> None:
    prev = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(_endpoint("POST", "/users", required_request_fields=("email",)),),
    )
    cur = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(
            _endpoint(
                "POST",
                "/users",
                required_request_fields=("email", "phone"),
            ),
        ),
    )
    result = diff_snapshots(previous=prev, current=cur)
    assert any(issue.rule_id == "COMPAT-ADDED-REQUIRED-REQUEST-FIELD" for issue in result.issues)


def test_changed_response_type(tmp_path: Path) -> None:
    prev = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(
            _endpoint(
                "GET",
                "/items",
                response_field_types=(("200:id", "integer"),),
            ),
        ),
    )
    cur = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(
            _endpoint(
                "GET",
                "/items",
                response_field_types=(("200:id", "string"),),
            ),
        ),
    )
    result = diff_snapshots(previous=prev, current=cur)
    assert any(issue.rule_id == "COMPAT-CHANGED-RESPONSE-TYPE" for issue in result.issues)


def test_identical_snapshots_produce_no_findings(tmp_path: Path) -> None:
    snap = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(_endpoint("GET", "/items"),),
    )
    result = diff_snapshots(previous=snap, current=snap)
    assert result.issues == ()


def test_snapshot_write_and_load_roundtrip(tmp_path: Path) -> None:
    snap = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(_endpoint("GET", "/items"),),
    )
    path = tmp_path / "api-schema.json"
    write_snapshot(path, snap)
    loaded = load_snapshot(path)
    assert loaded is not None
    assert loaded.endpoints == snap.endpoints


def test_load_previous_snapshot_explicit_run_id(tmp_path: Path) -> None:
    prev_dir = tmp_path / "RUN-PREV" / "api"
    prev_dir.mkdir(parents=True)
    snap = ApiSchemaSnapshot(
        schema_version=API_SCHEMA_SNAPSHOT_VERSION,
        source="openapi",
        endpoints=(_endpoint("GET", "/items"),),
    )
    write_snapshot(prev_dir / "api-schema.json", snap)
    loaded = load_previous_snapshot(
        artifacts_root=tmp_path,
        current_run_id="RUN-CURRENT",
        diff_since_run_id="RUN-PREV",
    )
    assert loaded is not None
    assert loaded.endpoints == snap.endpoints


def test_load_previous_snapshot_falls_back_to_latest_dir(tmp_path: Path) -> None:
    for name in ("RUN-1", "RUN-2", "RUN-3"):
        d = tmp_path / name / "api"
        d.mkdir(parents=True)
        snap = ApiSchemaSnapshot(
            schema_version=API_SCHEMA_SNAPSHOT_VERSION,
            source="openapi",
            endpoints=(_endpoint("GET", f"/items-{name}"),),
        )
        write_snapshot(d / "api-schema.json", snap)
    loaded = load_previous_snapshot(
        artifacts_root=tmp_path,
        current_run_id="RUN-3",  # exclude current
        diff_since_run_id=None,
    )
    assert loaded is not None
    # Latest non-current dir is RUN-2 (alphabetic order).
    assert loaded.endpoints[0].path == "/items-RUN-2"


def test_load_snapshot_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_snapshot(tmp_path / "missing.json") is None


def test_load_snapshot_invalid_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert load_snapshot(path) is None


def test_load_previous_snapshot_no_runs_returns_none(tmp_path: Path) -> None:
    assert (
        load_previous_snapshot(
            artifacts_root=tmp_path,
            current_run_id="RUN-CURRENT",
            diff_since_run_id=None,
        )
        is None
    )
