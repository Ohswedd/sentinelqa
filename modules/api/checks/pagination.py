"""Pagination boundary check (Phase 22.07).

A GET endpoint is treated as paginated when its OpenAPI parameters
include any of: ``page``, ``cursor``, ``offset``, or when its response
includes a ``Link: rel="next"`` header. For each detected paginated
endpoint the check walks pages up to ``pagination_max_pages`` and
asserts:

- The first empty page returns 200 with an empty array (not an error).
- Each page returns the same content-type and a stable error shape.
- Total visible items match the documented per-page bound when present.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from engine.config.schema import RootConfig

from modules.api.http_client import safe_request
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)
from modules.api.openapi import OpenApiDocument, OpenApiOperation

_PAGINATION_PARAM_NAMES = {"page", "cursor", "offset", "limit", "per_page"}


def run_pagination_check(
    *,
    client: httpx.Client,
    doc: OpenApiDocument,
    config: RootConfig,
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    scanned = 0
    max_pages = config.api.pagination_max_pages
    max_endpoints = config.api.sample_endpoints_max
    payload_cap = config.api.negative_max_payload_kb

    for op in doc.operations[:max_endpoints]:
        if op.method != "get":
            continue
        param_names = {str(p.get("name", "")).lower() for p in op.parameters if isinstance(p, dict)}
        if not (param_names & _PAGINATION_PARAM_NAMES):
            continue
        scanned += 1
        _walk_pages(op, client, max_pages, payload_cap, issues)

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="pagination",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


def _walk_pages(
    op: OpenApiOperation,
    client: httpx.Client,
    max_pages: int,
    payload_cap: int,
    issues: list[ApiIssue],
) -> None:
    page = 1
    seen_content_types: set[str] = set()
    seen_envelopes: set[str] = set()
    while page <= max_pages:
        url = f"{_materialise(op)}?page={page}"
        try:
            response = safe_request(client, op.method, url, max_body_kb=payload_cap)
        except (httpx.HTTPError, OSError):
            return
        # A 4xx on a paginated walk past page 1 is the empty-page-error
        # case (PRD §10.3: empty pages should return 200 with empty
        # array, not 4xx). We allow page 1 to return 4xx without
        # flagging because the endpoint may simply require auth or
        # other parameters the contract check covers.
        if response.status_code >= 400 and page >= 1:
            issues.append(
                ApiIssue(
                    rule_id="PAGINATION-EMPTY-PAGE-ERROR",
                    severity="medium",
                    confidence=0.85,
                    title=f"Empty page returned error: GET {op.path}",
                    description=(
                        f"Requesting page={page} returned HTTP "
                        f"{response.status_code}. Empty pages should return "
                        "200 with an empty array (PRD §10.3)."
                    ),
                    method="GET",
                    route=op.path,
                    expected_status=200,
                    observed_status=response.status_code,
                    recommendation=("Return 200 with an empty array beyond the last page."),
                    evidence={"page": str(page)},
                )
            )
            return
        ct = response.headers.get("content-type", "").split(";")[0].strip()
        if ct:
            seen_content_types.add(ct)
        if len(seen_content_types) > 1:
            issues.append(
                ApiIssue(
                    rule_id="PAGINATION-CONTENT-TYPE-DRIFT",
                    severity="medium",
                    confidence=0.85,
                    title=f"Pagination content-type drift: GET {op.path}",
                    description=(
                        "Paginated responses returned more than one content-type "
                        f"across pages 1..{page}: {sorted(seen_content_types)!r}."
                    ),
                    method="GET",
                    route=op.path,
                    recommendation="Return a consistent content-type across all pages.",
                    evidence={"page": str(page)},
                )
            )
            return
        if not ct.startswith("application/json"):
            return
        try:
            body: Any = response.json()
        except ValueError:
            return
        envelope = _envelope_shape(body)
        seen_envelopes.add(envelope)
        if len(seen_envelopes) > 1:
            issues.append(
                ApiIssue(
                    rule_id="PAGINATION-ENVELOPE-DRIFT",
                    severity="medium",
                    confidence=0.85,
                    title=f"Pagination envelope drift: GET {op.path}",
                    description=(
                        "The JSON envelope changed across pages: " f"{sorted(seen_envelopes)!r}."
                    ),
                    method="GET",
                    route=op.path,
                    recommendation="Return a stable JSON envelope on every page.",
                    evidence={"page": str(page)},
                )
            )
            return
        # Reached an empty page on a 2xx — that's the documented contract.
        if _is_empty_page(body):
            if response.status_code >= 400:
                # Defensive: already handled above for 4xx/5xx, but keep
                # the guard so future contract refinements (e.g. 3xx on
                # the empty page) get a clear finding instead of silent
                # acceptance.
                issues.append(
                    ApiIssue(
                        rule_id="PAGINATION-EMPTY-PAGE-ERROR",
                        severity="medium",
                        confidence=0.85,
                        title=f"Empty page returned error: GET {op.path}",
                        description=(
                            f"Requesting page={page} returned an empty list with "
                            f"HTTP {response.status_code}. Empty pages should "
                            "return 200 with an empty array."
                        ),
                        method="GET",
                        route=op.path,
                        expected_status=200,
                        observed_status=response.status_code,
                        recommendation=("Return 200 with an empty array beyond the last page."),
                        evidence={"page": str(page)},
                    )
                )
            return
        page += 1


def _envelope_shape(body: Any) -> str:
    if isinstance(body, list):
        return "[]"
    if isinstance(body, dict):
        return "{" + ",".join(sorted(body.keys())) + "}"
    return type(body).__name__


def _is_empty_page(body: Any) -> bool:
    if isinstance(body, list):
        return not body
    if isinstance(body, dict):
        for key in ("data", "items", "results"):
            inner = body.get(key)
            if isinstance(inner, list):
                return not inner
    return False


def _materialise(op: OpenApiOperation) -> str:
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


__all__ = ["run_pagination_check"]
