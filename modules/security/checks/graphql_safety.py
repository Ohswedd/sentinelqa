"""GraphQL safety probes.

Defensive-only probes for the four canonical GraphQL misconfiguration
classes the OWASP API Top-10 calls out: introspection-enabled-in-prod,
no depth limit, no complexity limit, and anonymous-mutation. Every
probe sends ONE request per class — there is no payload mutation,
no permutation generator, and no loop over an external corpus.
The safety guard at ``tests/security/test_no_offensive_checks.py``
asserts no other request shapes exist.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "graphql_safety"

_INTROSPECTION_QUERY: Final[str] = "{ __schema { types { name } } }"

# Fixed alias-bomb shape: five aliases for the same root field.
_COMPLEXITY_QUERY: Final[str] = (
    "{ a:__typename b:__typename c:__typename d:__typename e:__typename }"
)

# Fixed five-level depth shape using the spec-mandated ``__schema``
# subfields so we can issue it against ANY GraphQL server (no app-
# specific schema knowledge needed).
_DEPTH_QUERY: Final[str] = "{ __schema { types { fields { type { ofType { name } } } } } }"


@dataclass(frozen=True, slots=True)
class GraphqlProbeResult:
    """Outcome of one GraphQL probe."""

    endpoint: str
    introspection_accepted: bool
    depth_accepted: bool
    complexity_accepted: bool
    anonymous_mutation_accepted: bool
    mutation_name: str | None


def _response_is_data(payload: Any) -> bool:
    """True iff a GraphQL response carries a ``data`` field and no errors."""

    if not isinstance(payload, dict):
        return False
    if payload.get("errors"):
        return False
    return "data" in payload and payload["data"] is not None


def _post(
    client: httpx.Client, endpoint: str, query: str, *, headers: dict[str, str] | None = None
) -> Any:
    response = client.post(
        endpoint,
        json={"query": query},
        headers=headers or {},
        timeout=10.0,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return None


def probe_endpoint(
    client: httpx.Client,
    endpoint: str,
    *,
    mutation_to_probe: str | None = None,
) -> GraphqlProbeResult:
    """Run the four fixed probes against ``endpoint``."""

    try:
        introspection = _post(client, endpoint, _INTROSPECTION_QUERY)
    except httpx.HTTPError:
        introspection = None
    introspection_accepted = _response_is_data(introspection)

    try:
        depth = _post(client, endpoint, _DEPTH_QUERY)
    except httpx.HTTPError:
        depth = None
    depth_accepted = _response_is_data(depth)

    try:
        complexity = _post(client, endpoint, _COMPLEXITY_QUERY)
    except httpx.HTTPError:
        complexity = None
    complexity_accepted = _response_is_data(complexity)

    anon_accepted = False
    if mutation_to_probe is not None:
        # Probe with a minimal mutation invocation (no arguments).
        query = f"mutation {{ {mutation_to_probe} }}"
        try:
            response = _post(client, endpoint, query)
        except httpx.HTTPError:
            response = None
        anon_accepted = _response_is_data(response)

    return GraphqlProbeResult(
        endpoint=endpoint,
        introspection_accepted=introspection_accepted,
        depth_accepted=depth_accepted,
        complexity_accepted=complexity_accepted,
        anonymous_mutation_accepted=anon_accepted,
        mutation_name=mutation_to_probe,
    )


def evaluate_probe(probe: GraphqlProbeResult) -> Iterable[SecurityIssue]:
    if probe.introspection_accepted:
        yield SecurityIssue(
            rule_id="SEC-GRAPHQL-INTROSPECTION-ENABLED",
            severity="high",
            confidence=0.99,
            title="GraphQL introspection enabled in production",
            description=(
                f"The introspection query returned a schema at "
                f"{probe.endpoint}. Production should disable introspection."
            ),
            route=probe.endpoint,
            evidence={"endpoint": probe.endpoint, "cwe_id": "CWE-200"},
            recommendation=(
                "Disable introspection in production (e.g. Apollo " "`introspection: false`)."
            ),
        )
    if probe.depth_accepted:
        yield SecurityIssue(
            rule_id="SEC-GRAPHQL-NO-DEPTH-LIMIT",
            severity="medium",
            confidence=0.9,
            title="GraphQL endpoint accepts depth-5 query",
            description=(
                "A depth-5 nested query returned data. The endpoint has "
                "no depth limiter and is vulnerable to nested query "
                "resource-exhaustion."
            ),
            route=probe.endpoint,
            evidence={"endpoint": probe.endpoint, "cwe_id": "CWE-770"},
            recommendation=("Install a query-depth limiter; cap depth at ≤7."),
        )
    if probe.complexity_accepted:
        yield SecurityIssue(
            rule_id="SEC-GRAPHQL-NO-COMPLEXITY-LIMIT",
            severity="medium",
            confidence=0.9,
            title="GraphQL endpoint accepts alias-bomb query",
            description=(
                "A query with five aliases for the same field returned "
                "data. The endpoint has no query-cost analyser."
            ),
            route=probe.endpoint,
            evidence={"endpoint": probe.endpoint, "cwe_id": "CWE-770"},
            recommendation="Install a query-cost analyser.",
        )
    if probe.anonymous_mutation_accepted and probe.mutation_name:
        yield SecurityIssue(
            rule_id="SEC-GRAPHQL-MUTATION-NO-AUTH",
            severity="high",
            confidence=0.95,
            title="GraphQL mutation accepts anonymous requests",
            description=(
                f"Mutation `{probe.mutation_name}` accepted an "
                "anonymous request. CWE-862 / OWASP API-2023-05."
            ),
            route=probe.endpoint,
            evidence={
                "endpoint": probe.endpoint,
                "mutation": probe.mutation_name,
                "cwe_id": "CWE-862",
                "owasp_api_id": "API-2023-05",
            },
            recommendation=(
                "Gate every mutation behind authentication; assert "
                "identity before any state-changing resolver runs."
            ),
        )


def run_graphql_safety_check(
    ctx: CheckContext,
    *,
    endpoints: Sequence[str] | None = None,
    mutations: Sequence[str] | None = None,
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    targets = tuple(endpoints or ())
    if not targets:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=elapsed_ms,
            skipped=True,
            skipped_reason="no GraphQL endpoints discovered",
        )
    mutation_iter = list(mutations or [None] * len(targets))
    issues: list[SecurityIssue] = []
    for endpoint, mutation in zip(targets, mutation_iter, strict=False):
        probe = probe_endpoint(ctx.client, endpoint, mutation_to_probe=mutation)
        issues.extend(evaluate_probe(probe))
        _audit(
            ctx,
            kind="probe",
            detail=(
                f"ep={endpoint} intro={probe.introspection_accepted} "
                f"depth={probe.depth_accepted} cx={probe.complexity_accepted} "
                f"anon={probe.anonymous_mutation_accepted}"
            ),
        )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=len(targets),
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _audit(ctx: CheckContext, *, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "detail": detail,
        },
    )


# Exported so the safety guard can prove these are the ONLY probe shapes.
PROBE_QUERIES: Final[tuple[str, ...]] = (
    _INTROSPECTION_QUERY,
    _DEPTH_QUERY,
    _COMPLEXITY_QUERY,
)


__all__ = [
    "CHECK_NAME",
    "GraphqlProbeResult",
    "PROBE_QUERIES",
    "evaluate_probe",
    "probe_endpoint",
    "run_graphql_safety_check",
]
