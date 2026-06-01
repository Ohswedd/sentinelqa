"""OpenAPI contract check.

For each operation in the supplied :class:`OpenApiDocument` send a
sample request and validate the response status, content type, and
JSON body against the documented schema. Findings are emitted at:

- ``critical`` when an undocumented 5xx is returned.
- ``high`` for schema mismatch / wrong content-type / wrong status
 code at the highest documented severity bucket (5xx > 4xx > 3xx).
- ``medium`` for missing response fields the schema marked
 ``required``.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from engine.config.schema import RootConfig
from engine.domain.finding import Severity
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError

from modules.api.http_client import safe_request
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)
from modules.api.openapi import OpenApiDocument, OpenApiOperation

_SAFE_PROBE_METHODS = {"get", "head", "options"}


def run_openapi_contract_check(
    *,
    client: httpx.Client,
    doc: OpenApiDocument,
    config: RootConfig,
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    scanned = 0
    max_endpoints = config.api.sample_endpoints_max
    for op in doc.operations[:max_endpoints]:
        scanned += 1
        # Only safe methods are probed by the contract check. Mutating
        # methods (POST/PUT/PATCH/DELETE) are exercised by the negative
        # / auth checks with controlled bodies; the contract check is
        # read-only by design.
        if op.method not in _SAFE_PROBE_METHODS:
            continue
        try:
            url = _materialise_url(op)
            response = safe_request(
                client,
                op.method,
                url,
                max_body_kb=config.api.negative_max_payload_kb,
            )
        except (httpx.HTTPError, OSError) as exc:
            issues.append(
                ApiIssue(
                    rule_id="CONTRACT-NETWORK",
                    severity="medium",
                    confidence=0.6,
                    title=f"Contract probe failed: {op.method.upper()} {op.path}",
                    description=(
                        "The contract probe could not reach the endpoint. "
                        "This may indicate the target was unreachable or "
                        "produced an invalid HTTP response."
                    ),
                    method=op.method.upper(),
                    route=op.path,
                    recommendation=(
                        "Verify the target is reachable and that the path is "
                        "correctly templated in the OpenAPI spec."
                    ),
                    evidence={"error": exc.__class__.__name__, "message": str(exc)[:240]},
                )
            )
            continue

        _evaluate_response(op, response, issues)

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="contract",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


def _materialise_url(op: OpenApiOperation) -> str:
    """Fill OpenAPI path parameters with safe placeholder values."""

    url = op.path
    for parameter in op.parameters:
        if parameter.get("in") != "path":
            continue
        name = parameter.get("name")
        if not isinstance(name, str):
            continue
        schema = parameter.get("schema") or {}
        ptype = schema.get("type") if isinstance(schema, dict) else None
        placeholder = "1" if ptype in {"integer", "number"} else "sample"
        url = url.replace("{" + name + "}", placeholder)
    return url


def _evaluate_response(
    op: OpenApiOperation,
    response: httpx.Response,
    issues: list[ApiIssue],
) -> None:
    status = response.status_code
    documented_statuses = set(op.response_schemas.keys()) | {0}
    if status not in documented_statuses and status != 0:
        # Surface 5xx as critical (server crash on a documented happy path),
        # 4xx as high (the doc claims this endpoint accepts the probe),
        # 3xx/other as medium.
        severity: Severity = (
            "critical" if status >= 500 else ("high" if status >= 400 else "medium")
        )
        issues.append(
            ApiIssue(
                rule_id="CONTRACT-STATUS",
                severity=severity,
                confidence=0.85,
                title=f"Undocumented status: {op.method.upper()} {op.path} → {status}",
                description=(
                    "Server returned a status code not documented in the "
                    "OpenAPI spec for this operation."
                ),
                method=op.method.upper(),
                route=op.path,
                expected_status=_first_documented_2xx(op) or None,
                observed_status=status,
                recommendation=(
                    "Update the OpenAPI spec to include this status code, or "
                    "fix the server so it returns a documented response."
                ),
                evidence={
                    "documented_statuses": ",".join(sorted(str(s) for s in op.response_schemas))
                },
            )
        )
        return

    response_schema = op.response_schemas.get(status)
    if response_schema is None:
        response_schema = op.response_schemas.get(0)  # default
    if response_schema is None:
        return

    expected_content_type = op.response_content_type.get(status) or op.response_content_type.get(0)
    actual_content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if (
        expected_content_type
        and actual_content_type
        and not actual_content_type.startswith(expected_content_type)
    ):
        issues.append(
            ApiIssue(
                rule_id="CONTRACT-CONTENT-TYPE",
                severity="medium",
                confidence=0.8,
                title=f"Unexpected content-type: {op.method.upper()} {op.path}",
                description=(
                    f"Documented content-type {expected_content_type!r}; "
                    f"server returned {actual_content_type!r}."
                ),
                method=op.method.upper(),
                route=op.path,
                expected_status=status,
                observed_status=status,
                recommendation=(
                    "Update the spec or the server so the response content-type "
                    "matches the contract."
                ),
                evidence={
                    "expected": expected_content_type,
                    "observed": actual_content_type or "(empty)",
                },
            )
        )

    if actual_content_type.startswith("application/json"):
        try:
            body: Any = response.json()
        except ValueError:
            issues.append(
                ApiIssue(
                    rule_id="CONTRACT-INVALID-JSON",
                    severity="high",
                    confidence=0.95,
                    title=f"Invalid JSON: {op.method.upper()} {op.path}",
                    description="Server claimed application/json but body was not valid JSON.",
                    method=op.method.upper(),
                    route=op.path,
                    expected_status=status,
                    observed_status=status,
                    recommendation="Return valid JSON or update the documented content-type.",
                    evidence={"body_preview": response.text[:200]},
                )
            )
            return
        validator = Draft7Validator(response_schema)
        errors = list(validator.iter_errors(body))
        for err in errors[:5]:  # cap per-endpoint noise
            issues.append(_schema_violation(op, status, err))


def _schema_violation(op: OpenApiOperation, status: int, err: ValidationError) -> ApiIssue:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    is_missing_required = str(err.validator) == "required"
    severity: Severity = "high" if not is_missing_required else "medium"
    return ApiIssue(
        rule_id="CONTRACT-SCHEMA" if not is_missing_required else "CONTRACT-MISSING-FIELD",
        severity=severity,
        confidence=0.85,
        title=f"Response schema violation at {path}",
        description=err.message[:1000],
        method=op.method.upper(),
        route=op.path,
        expected_status=status,
        observed_status=status,
        recommendation=(
            "Align the server's response with the OpenAPI schema, or update the "
            "schema if the response is intentionally different."
        ),
        evidence={"json_path": path, "validator": str(err.validator)},
    )


def _first_documented_2xx(op: OpenApiOperation) -> int | None:
    for status in sorted(op.response_schemas):
        if 200 <= status < 300:
            return status
    return None


__all__ = ["run_openapi_contract_check"]
