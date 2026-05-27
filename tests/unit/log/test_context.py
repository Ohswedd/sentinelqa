"""LogContext tests (context-var stack + run-id binding)."""

from __future__ import annotations

from engine.log.context import LogContext, current_context


def test_push_pop_round_trip() -> None:
    token = LogContext.push({"k": "v"})
    try:
        assert current_context()["k"] == "v"
    finally:
        LogContext.pop(token)
    assert "k" not in current_context()


def test_nested_push() -> None:
    outer = LogContext.push({"a": 1})
    inner = LogContext.push({"b": 2})
    try:
        ctx = current_context()
        assert ctx == {"a": 1, "b": 2}
    finally:
        LogContext.pop(inner)
        LogContext.pop(outer)


def test_bind_run_id() -> None:
    LogContext.bind_run_id("RUN-AAAAAAAAAAAA")
    assert current_context()["run_id"] == "RUN-AAAAAAAAAAAA"
    # Cleanup so test order doesn't leak.
    from engine.log import context as ctx_mod

    ctx_mod._CONTEXT.set({})
