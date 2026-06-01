"""Auth-matrix check.

For each authenticated operation in the supplied OpenAPI document we
issue three probes:

- Anonymous (no Authorization header) → expect 401/403.
- Expired-token sentinel ("Bearer expired-token") → expect 401.
- Cross-user token (each configured ``auth_test_users`` entry) → still
 expect 401/403 if the endpoint is sensitive to caller identity.

Any 2xx is critical (unauthorized access). The expired-token probe
uses a fixed string so the probe never carries a valid credential; we
do NOT mint or rotate tokens.

If no OpenAPI doc is loaded but ``config.api.routes`` lists explicit
paths, fall back to probing those with the same matrix.
"""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter

import httpx
from engine.config.schema import RootConfig
from engine.domain.finding import Severity

from modules.api.http_client import safe_request
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)
from modules.api.openapi import OpenApiDocument, OpenApiOperation

_EXPIRED_TOKEN = "Bearer expired-token-sentinelqa-probe"
_AUTH_SAFE_METHODS = {"get", "head", "options"}


def run_auth_check(
    *,
    client: httpx.Client,
    doc: OpenApiDocument | None,
    config: RootConfig,
    env: Mapping[str, str],
) -> ApiCheckResult:
    started = perf_counter()
    issues: list[ApiIssue] = []
    scanned = 0
    max_endpoints = config.api.sample_endpoints_max
    payload_cap = config.api.negative_max_payload_kb

    candidates: list[tuple[str, str]] = []
    if doc is not None:
        for op in doc.authenticated_operations()[:max_endpoints]:
            if op.method not in _AUTH_SAFE_METHODS:
                continue
            candidates.append((op.method.upper(), _materialise(op)))
    else:
        for route in config.api.routes[:max_endpoints]:
            candidates.append(("GET", route))

    if not candidates:
        duration_ms = int((perf_counter() - started) * 1000)
        return ApiCheckResult(
            schema_version=API_RESULT_SCHEMA_VERSION,
            check="auth",
            issues=(),
            targets_scanned=0,
            duration_ms=duration_ms,
            skipped=True,
            skip_reason=("no authenticated OpenAPI operations and no api.routes configured"),
        )

    cross_user_tokens: list[tuple[str, str]] = []
    for user in config.api.auth_test_users:
        if user.token_env and user.token_env in env and env[user.token_env]:
            cross_user_tokens.append((user.label, env[user.token_env]))

    for method, url in candidates:
        scanned += 1
        _probe(client, method, url, None, "anonymous", payload_cap, issues)
        _probe(client, method, url, _EXPIRED_TOKEN, "expired_token", payload_cap, issues)
        for label, token in cross_user_tokens:
            _probe(
                client,
                method,
                url,
                f"Bearer {token}",
                f"cross_user:{label}",
                payload_cap,
                issues,
            )

    duration_ms = int((perf_counter() - started) * 1000)
    return ApiCheckResult(
        schema_version=API_RESULT_SCHEMA_VERSION,
        check="auth",
        issues=tuple(issues),
        targets_scanned=scanned,
        duration_ms=duration_ms,
    )


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


def _probe(
    client: httpx.Client,
    method: str,
    url: str,
    auth_header: str | None,
    label: str,
    payload_cap: int,
    issues: list[ApiIssue],
) -> None:
    headers: dict[str, str] = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    try:
        response = safe_request(
            client,
            method,
            url,
            headers=headers,
            max_body_kb=payload_cap,
        )
    except (httpx.HTTPError, OSError):
        return
    status = response.status_code
    if 200 <= status < 300:
        is_anonymous = label == "anonymous"
        severity: Severity = "critical" if is_anonymous else "high"
        issues.append(
            ApiIssue(
                rule_id=f"AUTH-UNAUTHORIZED-{label.upper().replace(':', '-')}",
                severity=severity,
                confidence=0.9,
                title=f"Unauthorized 2xx: {method} {url} ({label})",
                description=(
                    "The endpoint is documented as authenticated, but it "
                    f"returned {status} for an unauthorized request "
                    f"({label})."
                ),
                method=method,
                route=url,
                expected_status=401,
                observed_status=status,
                recommendation=(
                    "Reject this request with 401 (anonymous / expired) or "
                    "403 (insufficient permissions). Never expose an "
                    "authenticated resource to an unauthorized caller."
                ),
                evidence={"variant": label},
            )
        )


__all__ = ["run_auth_check"]
