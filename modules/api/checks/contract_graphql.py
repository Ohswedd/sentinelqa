"""GraphQL contract check.

For each probeable operation in the supplied :class:`GraphqlSchema`,
issue a single ``POST <graphql_endpoint>`` with ``{"query": "..."}``
and validate:

- The HTTP response is 200 with content-type ``application/json``.
- The JSON body has the documented ``data.<field>`` path.
- Non-nullable response fields are not ``null``.
- Top-level error array is empty for fields without arguments.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from engine.config.schema import RootConfig

from modules.api.graphql import GraphqlSchema
from modules.api.http_client import safe_request
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)


def run_graphql_contract_check(
    *,
    client: httpx.Client,
    schema: GraphqlSchema,
    config: RootConfig,
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    scanned = 0
    endpoint = config.api.graphql_endpoint
    max_endpoints = config.api.sample_endpoints_max
    for op in schema.operations[:max_endpoints]:
        scanned += 1
        if op.kind == "mutation":
            # Mutations write state. Skip probing them unless explicit
            # auth/negative paths exercise them.
            continue
        query_text = f"{op.kind} {{ {op.field_name}{op.selection} }}"
        try:
            response = safe_request(
                client,
                "POST",
                endpoint,
                headers={"Content-Type": "application/json"},
                json_body={"query": query_text},
                max_body_kb=config.api.negative_max_payload_kb,
            )
        except (httpx.HTTPError, OSError) as exc:
            issues.append(
                ApiIssue(
                    rule_id="GRAPHQL-NETWORK",
                    severity="medium",
                    confidence=0.6,
                    title=f"GraphQL probe failed: {op.kind} {op.field_name}",
                    description=(
                        "The GraphQL probe could not reach the endpoint. "
                        f"Network error: {exc.__class__.__name__}."
                    ),
                    method="POST",
                    route=endpoint,
                    recommendation="Verify the GraphQL endpoint is reachable.",
                    evidence={"query": query_text[:200]},
                )
            )
            continue

        _evaluate_graphql_response(op, query_text, endpoint, response, issues)

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="contract",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


def _evaluate_graphql_response(
    op: Any,
    query_text: str,
    endpoint: str,
    response: httpx.Response,
    issues: list[ApiIssue],
) -> None:
    status = response.status_code
    if status != 200:
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-STATUS",
                severity="high" if status >= 500 else "medium",
                confidence=0.9,
                title=f"GraphQL HTTP {status}: {op.field_name}",
                description=(
                    "GraphQL responses are conventionally HTTP 200 even on "
                    f"resolver errors. Server returned {status}."
                ),
                method="POST",
                route=endpoint,
                expected_status=200,
                observed_status=status,
                recommendation=(
                    "Return HTTP 200 and surface resolver errors via the " "'errors' array."
                ),
                evidence={"query": query_text[:200]},
            )
        )
        return

    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if not content_type.startswith("application/json"):
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-CONTENT-TYPE",
                severity="medium",
                confidence=0.8,
                title=f"GraphQL content-type: {op.field_name}",
                description=(f"GraphQL responses must be JSON; got {content_type!r}."),
                method="POST",
                route=endpoint,
                recommendation="Set Content-Type to application/json.",
                evidence={"observed": content_type or "(empty)"},
            )
        )
        return

    try:
        body: Any = response.json()
    except ValueError:
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-INVALID-JSON",
                severity="high",
                confidence=0.95,
                title=f"GraphQL invalid JSON: {op.field_name}",
                description="GraphQL endpoint returned non-JSON body.",
                method="POST",
                route=endpoint,
                recommendation="Return valid JSON.",
                evidence={"body_preview": response.text[:200]},
            )
        )
        return

    if not isinstance(body, dict):
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-SHAPE",
                severity="high",
                confidence=0.9,
                title=f"GraphQL shape: {op.field_name}",
                description=(
                    "GraphQL responses must be a JSON object containing "
                    "'data' and/or 'errors' keys."
                ),
                method="POST",
                route=endpoint,
                recommendation="Return a JSON object per the GraphQL over HTTP spec.",
                evidence={"body_type": type(body).__name__},
            )
        )
        return

    errors_array = body.get("errors")
    if isinstance(errors_array, list) and errors_array:
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-RESOLVER-ERROR",
                severity="medium",
                confidence=0.8,
                title=f"GraphQL resolver error: {op.field_name}",
                description=(
                    "Argument-less probe triggered resolver errors — the "
                    "field is exposed but unresolvable in its default "
                    "configuration."
                ),
                method="POST",
                route=endpoint,
                recommendation=(
                    "Either hide the field, fix the resolver, or document the "
                    "expected argument set."
                ),
                evidence={"first_error": str(errors_array[0])[:240]},
            )
        )

    data = body.get("data")
    if data is None and op.return_non_null:
        issues.append(
            ApiIssue(
                rule_id="GRAPHQL-NULL-NON-NULL",
                severity="high",
                confidence=0.9,
                title=f"Non-nullable field returned null: {op.field_name}",
                description=(
                    "The schema declares this field as non-nullable, but the "
                    "resolver returned null."
                ),
                method="POST",
                route=endpoint,
                recommendation=("Fix the resolver, or mark the schema field nullable."),
                evidence={"field": op.field_name},
            )
        )
        return

    if isinstance(data, dict):
        value = data.get(op.field_name)
        if value is None and op.return_non_null:
            issues.append(
                ApiIssue(
                    rule_id="GRAPHQL-NULL-NON-NULL",
                    severity="high",
                    confidence=0.9,
                    title=f"Non-nullable field returned null: {op.field_name}",
                    description=("Schema declares non-nullable; resolver returned null."),
                    method="POST",
                    route=endpoint,
                    recommendation="Fix the resolver or mark the field nullable.",
                    evidence={"field": op.field_name},
                )
            )
        elif isinstance(value, dict):
            for required in op.required_fields:
                if value.get(required) is None:
                    issues.append(
                        ApiIssue(
                            rule_id="GRAPHQL-MISSING-FIELD",
                            severity="high",
                            confidence=0.85,
                            title=(
                                f"GraphQL non-nullable subfield missing: "
                                f"{op.field_name}.{required}"
                            ),
                            description=(
                                "Schema declares this subfield non-nullable, "
                                "but the response is null or absent."
                            ),
                            method="POST",
                            route=endpoint,
                            recommendation=("Fix the resolver to always populate this field."),
                            evidence={"path": f"{op.field_name}.{required}"},
                        )
                    )


__all__ = ["run_graphql_contract_check"]
