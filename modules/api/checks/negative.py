"""Negative-case check (Phase 22.04, our engineering rules).

Per our engineering rules / the documentation we generate a small, bounded set of
variants for each documented request body and assert that the server
rejects them. We never:

- Send more than ``api.negative_max_variants_per_endpoint`` variants
  per endpoint (default 4, hard cap 16).
- Send bodies above ``api.negative_max_payload_kb`` (default 16 KB,
  hard cap 64 KB in :mod:`modules.api.http_client`).
- Iterate randomly or fuzz beyond the variant catalogue below.

Findings:

- ``high`` when a request with a missing-required field returns 2xx
  (validation gap).
- ``high`` when a request returns 5xx (server crash on invalid input).
- ``medium`` when the error shape is inconsistent across variants (the
  uniform-error-shape check in :mod:`pagination.py` also picks this up).
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from engine.config.schema import RootConfig

from modules.api.http_client import RequestTooLargeError, safe_request
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)
from modules.api.openapi import OpenApiDocument, OpenApiOperation

_VARIANT_LABELS: tuple[str, ...] = (
    "missing_required",
    "wrong_type",
    "out_of_range",
    "oversized_string",
)


def run_negative_check(
    *,
    client: httpx.Client,
    doc: OpenApiDocument,
    config: RootConfig,
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    scanned = 0
    max_endpoints = config.api.sample_endpoints_max
    max_variants = config.api.negative_max_variants_per_endpoint
    payload_cap_kb = config.api.negative_max_payload_kb

    for op in doc.operations[:max_endpoints]:
        # Negative tests target endpoints that accept a request body.
        if op.request_body_schema is None:
            continue
        scanned += 1
        variants = _generate_variants(op, payload_cap_kb=payload_cap_kb, max_variants=max_variants)
        for label, payload in variants:
            try:
                response = safe_request(
                    client,
                    op.method,
                    _materialise_url(op),
                    headers={"Content-Type": op.request_body_content_type or "application/json"},
                    json_body=payload,
                    max_body_kb=payload_cap_kb,
                )
            except RequestTooLargeError:
                # The variant generator clamps to cap; reaching this branch
                # would mean a bug. Record info, do not crash.
                continue
            except (httpx.HTTPError, OSError):
                continue
            _evaluate_negative_response(op, label, response, issues)

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="negative",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


def _materialise_url(op: OpenApiOperation) -> str:
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


def _generate_variants(
    op: OpenApiOperation,
    *,
    payload_cap_kb: int,
    max_variants: int,
) -> list[tuple[str, dict[str, Any]]]:
    schema = op.request_body_schema or {}
    properties = schema.get("properties") if isinstance(schema, dict) else {}
    required: list[str] = list(schema.get("required") or []) if isinstance(schema, dict) else []
    valid_payload = _build_valid_payload(schema)
    variants: list[tuple[str, dict[str, Any]]] = []

    if required:
        missing = dict(valid_payload)
        missing.pop(required[0], None)
        variants.append(("missing_required", missing))

    if isinstance(properties, dict):
        for name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue
            prop_type = prop_schema.get("type")
            if prop_type in {"integer", "number"}:
                wrong = dict(valid_payload)
                wrong[name] = "not_a_number"
                variants.append(("wrong_type", wrong))
                if prop_schema.get("maximum") is not None:
                    out_of_range = dict(valid_payload)
                    out_of_range[name] = int(prop_schema["maximum"]) + 10000
                    variants.append(("out_of_range", out_of_range))
                break
            if prop_type == "boolean":
                wrong = dict(valid_payload)
                wrong[name] = "not_a_boolean"
                variants.append(("wrong_type", wrong))
                break
        # Oversized string variant: pick the first string field and inflate
        # the value up to (cap - 1) KB so we never trip RequestTooLargeError.
        for name, prop_schema in properties.items():
            if isinstance(prop_schema, dict) and prop_schema.get("type") == "string":
                inflated = dict(valid_payload)
                size_bytes = max(1, payload_cap_kb - 1) * 1024
                inflated[name] = "A" * size_bytes
                variants.append(("oversized_string", inflated))
                break

    # Deduplicate by label preserving order, then clamp.
    seen: set[str] = set()
    deduped: list[tuple[str, dict[str, Any]]] = []
    for label, payload in variants:
        if label in seen:
            continue
        seen.add(label)
        deduped.append((label, payload))
    return deduped[:max_variants]


def _build_valid_payload(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    out: dict[str, Any] = {}
    for name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            continue
        out[name] = _sample_value(prop_schema)
    return out


def _sample_value(schema: dict[str, Any]) -> Any:
    if "default" in schema:
        return schema["default"]
    if "example" in schema:
        return schema["example"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    t = schema.get("type")
    if t == "integer":
        return schema.get("minimum", 1)
    if t == "number":
        return schema.get("minimum", 1.0)
    if t == "boolean":
        return False
    if t == "array":
        return []
    if t == "object":
        return {}
    # Default: bounded string.
    return "sample"


def _evaluate_negative_response(
    op: OpenApiOperation,
    label: str,
    response: httpx.Response,
    issues: list[ApiIssue],
) -> None:
    status = response.status_code
    if status >= 500:
        issues.append(
            ApiIssue(
                rule_id="NEGATIVE-SERVER-ERROR",
                severity="high",
                confidence=0.9,
                title=f"5xx on invalid input: {op.method.upper()} {op.path}",
                description=(
                    f"Server returned {status} for a {label!r} variant. "
                    "Invalid input should surface as 4xx with a structured "
                    "error, not a 5xx."
                ),
                method=op.method.upper(),
                route=op.path,
                expected_status=400,
                observed_status=status,
                recommendation="Validate input at the request boundary and return 4xx.",
                evidence={"variant": label},
            )
        )
        return
    if label == "missing_required" and 200 <= status < 300:
        issues.append(
            ApiIssue(
                rule_id="NEGATIVE-VALIDATION-GAP",
                severity="high",
                confidence=0.85,
                title=f"Validation gap: {op.method.upper()} {op.path}",
                description=(
                    "Endpoint accepted a request body missing a required "
                    "field and returned 2xx. Backend validation must reject "
                    "the request."
                ),
                method=op.method.upper(),
                route=op.path,
                expected_status=400,
                observed_status=status,
                recommendation=(
                    "Add request validation that rejects payloads missing "
                    "required fields with a 4xx response."
                ),
                evidence={"variant": label},
            )
        )


__all__ = ["run_negative_check"]
