"""Backward-compatibility check + snapshot persistence.

Each run writes ``<run-dir>/api/api-schema.json`` capturing the
:class:`ApiSchemaSnapshot` derived from the loaded OpenAPI / GraphQL
doc. The backward-compat check loads the *previous* snapshot (either
``--diff-since <run-id>`` or, when unspecified, the alphabetically
last sibling run directory) and emits findings for breaking changes:

- Removed endpoint → high.
- Removed required response field → high.
- Changed response field type → high.
- Added required request field → medium-high.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
    ApiSchemaEndpoint,
    ApiSchemaSnapshot,
)


def write_snapshot(path: Path, snapshot: ApiSchemaSnapshot) -> None:
    path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_snapshot(path: Path) -> ApiSchemaSnapshot | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return ApiSchemaSnapshot(**data)
    except Exception:
        return None


def load_previous_snapshot(
    *,
    artifacts_root: Path,
    current_run_id: str,
    diff_since_run_id: str | None,
) -> ApiSchemaSnapshot | None:
    """Locate the snapshot from a prior run.

    Resolution order:

    1. ``diff_since_run_id`` if supplied; load
    ``<artifacts_root>/<id>/api/api-schema.json``.
    2. Otherwise pick the alphabetically last run dir whose id != current
    and which has an ``api/api-schema.json``.
    """

    if not artifacts_root.exists():
        return None
    if diff_since_run_id is not None:
        explicit = artifacts_root / diff_since_run_id / "api" / "api-schema.json"
        return load_snapshot(explicit)
    candidates: list[Path] = []
    for entry in artifacts_root.iterdir():
        if not entry.is_dir() or entry.name == current_run_id:
            continue
        path = entry / "api" / "api-schema.json"
        if path.exists():
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.parent.parent.name)
    return load_snapshot(candidates[-1])


def diff_snapshots(
    *,
    previous: ApiSchemaSnapshot,
    current: ApiSchemaSnapshot,
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    prev_index: dict[tuple[str, str], ApiSchemaEndpoint] = {
        (e.method, e.path): e for e in previous.endpoints
    }
    cur_index: dict[tuple[str, str], ApiSchemaEndpoint] = {
        (e.method, e.path): e for e in current.endpoints
    }

    for key, prev in sorted(prev_index.items()):
        if key not in cur_index:
            issues.append(
                ApiIssue(
                    rule_id="COMPAT-REMOVED-ENDPOINT",
                    severity="high",
                    confidence=0.95,
                    title=f"Removed endpoint: {prev.method} {prev.path}",
                    description=(
                        "Endpoint present in the previous schema snapshot is "
                        "absent in the current snapshot."
                    ),
                    method=prev.method,
                    route=prev.path,
                    recommendation=(
                        "If removal is intentional, document the deprecation "
                        "and increment the major API version."
                    ),
                    evidence={"previous_source": previous.source},
                )
            )
            continue
        cur = cur_index[key]
        missing_required_response = set(prev.required_response_fields) - set(
            cur.required_response_fields
        )
        for field_name in sorted(missing_required_response):
            issues.append(
                ApiIssue(
                    rule_id="COMPAT-REMOVED-REQUIRED-RESPONSE-FIELD",
                    severity="high",
                    confidence=0.9,
                    title=(
                        f"Removed required response field: {prev.method} "
                        f"{prev.path} ({field_name})"
                    ),
                    description=(
                        "Field marked 'required' in the previous schema is no "
                        "longer required in the current schema."
                    ),
                    method=prev.method,
                    route=prev.path,
                    recommendation=(
                        "Either keep the field required or bump the major API " "version."
                    ),
                    evidence={"field": field_name},
                )
            )
        added_required_request = set(cur.required_request_fields) - set(
            prev.required_request_fields
        )
        for field_name in sorted(added_required_request):
            issues.append(
                ApiIssue(
                    rule_id="COMPAT-ADDED-REQUIRED-REQUEST-FIELD",
                    severity="high",
                    confidence=0.9,
                    title=(
                        f"Added required request field: {prev.method} "
                        f"{prev.path} ({field_name})"
                    ),
                    description=(
                        "A request field marked 'required' did not exist as "
                        "required in the previous schema."
                    ),
                    method=prev.method,
                    route=prev.path,
                    recommendation=(
                        "Make the field optional, supply a default, or bump the "
                        "major API version."
                    ),
                    evidence={"field": field_name},
                )
            )
        prev_types = dict(prev.response_field_types)
        cur_types = dict(cur.response_field_types)
        for field_name, prev_type in prev_types.items():
            cur_type = cur_types.get(field_name)
            if cur_type is not None and cur_type != prev_type:
                issues.append(
                    ApiIssue(
                        rule_id="COMPAT-CHANGED-RESPONSE-TYPE",
                        severity="high",
                        confidence=0.9,
                        title=(
                            f"Changed response field type: {prev.method} "
                            f"{prev.path} ({field_name}: {prev_type} → {cur_type})"
                        ),
                        description=(
                            "A response field's type changed between schema " "snapshots."
                        ),
                        method=prev.method,
                        route=prev.path,
                        recommendation=(
                            "Type changes are breaking — keep the old type or "
                            "bump the major API version."
                        ),
                        evidence={
                            "field": field_name,
                            "previous_type": prev_type,
                            "current_type": cur_type,
                        },
                    )
                )

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="backward_compat",
        issues=tuple(issues),
        targets_scanned=len(prev_index),
        duration_ms=duration_ms,
    )


__all__ = [
    "diff_snapshots",
    "load_previous_snapshot",
    "load_snapshot",
    "write_snapshot",
]
