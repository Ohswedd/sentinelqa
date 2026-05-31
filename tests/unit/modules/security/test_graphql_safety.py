"""Unit tests for :mod:`modules.security.checks.graphql_safety` (task 32.04)."""

from __future__ import annotations

from collections.abc import Iterable

from modules.security.checks.graphql_safety import (
    PROBE_QUERIES,
    GraphqlProbeResult,
    _response_is_data,
    evaluate_probe,
)
from modules.security.models import SecurityIssue


def _ids(issues: Iterable[SecurityIssue]) -> set[str]:
    return {i.rule_id for i in issues}


def test_response_is_data_recognises_canonical_shape() -> None:
    assert _response_is_data({"data": {"__schema": {"types": []}}}) is True
    assert _response_is_data({"data": None}) is False
    assert _response_is_data({"errors": [{"message": "denied"}]}) is False
    assert _response_is_data(None) is False


def test_evaluate_probe_emits_introspection_finding() -> None:
    probe = GraphqlProbeResult(
        endpoint="https://api/graphql",
        introspection_accepted=True,
        depth_accepted=False,
        complexity_accepted=False,
        anonymous_mutation_accepted=False,
        mutation_name=None,
    )
    assert "SEC-GRAPHQL-INTROSPECTION-ENABLED" in _ids(evaluate_probe(probe))


def test_evaluate_probe_emits_depth_finding() -> None:
    probe = GraphqlProbeResult(
        endpoint="https://api/graphql",
        introspection_accepted=False,
        depth_accepted=True,
        complexity_accepted=False,
        anonymous_mutation_accepted=False,
        mutation_name=None,
    )
    assert "SEC-GRAPHQL-NO-DEPTH-LIMIT" in _ids(evaluate_probe(probe))


def test_evaluate_probe_emits_complexity_finding() -> None:
    probe = GraphqlProbeResult(
        endpoint="https://api/graphql",
        introspection_accepted=False,
        depth_accepted=False,
        complexity_accepted=True,
        anonymous_mutation_accepted=False,
        mutation_name=None,
    )
    assert "SEC-GRAPHQL-NO-COMPLEXITY-LIMIT" in _ids(evaluate_probe(probe))


def test_evaluate_probe_emits_mutation_finding() -> None:
    probe = GraphqlProbeResult(
        endpoint="https://api/graphql",
        introspection_accepted=False,
        depth_accepted=False,
        complexity_accepted=False,
        anonymous_mutation_accepted=True,
        mutation_name="deleteUser",
    )
    issues = list(evaluate_probe(probe))
    found = next(i for i in issues if i.rule_id == "SEC-GRAPHQL-MUTATION-NO-AUTH")
    assert found.evidence.get("owasp_api_id") == "API-2023-05"


def test_clean_probe_has_no_findings() -> None:
    probe = GraphqlProbeResult(
        endpoint="https://api/graphql",
        introspection_accepted=False,
        depth_accepted=False,
        complexity_accepted=False,
        anonymous_mutation_accepted=False,
        mutation_name=None,
    )
    assert list(evaluate_probe(probe)) == []


def test_probe_query_set_is_fixed() -> None:
    # CLAUDE §6 + ADR-0044 safety boundary: the probe queries are a
    # fixed, enumerated tuple. Drift here breaks the safety guarantee.
    assert len(PROBE_QUERIES) == 3
    for query in PROBE_QUERIES:
        assert isinstance(query, str)
        assert "{" in query and "}" in query
