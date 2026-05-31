"""Unit tests for :mod:`modules.security.checks.api_bola_bfla` (task 32.05)."""

from __future__ import annotations

from modules.security.checks.api_bola_bfla import (
    CapturedCall,
    classify_replay,
    evaluate_classification,
)


def _ids(issues):
    return {i.rule_id for i in issues}


def test_classify_bola_when_body_shape_matches_and_id_in_path() -> None:
    captured = CapturedCall(
        method="GET",
        url="https://api/users/42/profile",
        body_shape=("email", "id", "name"),
    )
    body = {"id": 42, "name": "Alice", "email": "alice@example.com"}
    assert classify_replay(captured, 200, body, b_is_admin=False) == "bola"


def test_classify_bfla_when_admin_path_and_non_admin_identity() -> None:
    captured = CapturedCall(
        method="POST",
        url="https://api/admin/users",
        body_shape=("created",),
    )
    assert classify_replay(captured, 204, None, b_is_admin=False) == "bfla"


def test_classify_clean_when_response_is_403() -> None:
    captured = CapturedCall(
        method="GET",
        url="https://api/users/42/profile",
        body_shape=("id",),
    )
    assert classify_replay(captured, 403, None, b_is_admin=False) == "clean"


def test_classify_clean_when_body_shape_differs() -> None:
    captured = CapturedCall(
        method="GET",
        url="https://api/users/42/profile",
        body_shape=("email", "id", "name"),
    )
    body = {"error": "not allowed"}
    assert classify_replay(captured, 200, body, b_is_admin=False) == "clean"


def test_evaluate_bola_emits_owasp_id() -> None:
    captured = CapturedCall(
        method="GET",
        url="https://api/users/42",
        body_shape=("id",),
    )
    issues = list(evaluate_classification(captured, "bola"))
    assert issues
    assert issues[0].evidence.get("owasp_api_id") == "API-2023-01"


def test_evaluate_bfla_emits_owasp_id() -> None:
    captured = CapturedCall(
        method="POST",
        url="https://api/admin/users",
        body_shape=(),
    )
    issues = list(evaluate_classification(captured, "bfla"))
    assert issues
    assert issues[0].evidence.get("owasp_api_id") == "API-2023-03"


def test_evaluate_clean_emits_nothing() -> None:
    captured = CapturedCall(method="GET", url="https://api/foo", body_shape=())
    assert list(evaluate_classification(captured, "clean")) == []
