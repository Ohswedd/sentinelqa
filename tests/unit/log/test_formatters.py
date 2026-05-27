"""Formatter tests."""

from __future__ import annotations

import json
import logging

import pytest
from engine.log.context import LogContext
from engine.log.formatters import HumanFormatter, JSONFormatter


@pytest.fixture(autouse=True)
def _reset_context() -> None:
    # Clear any bound context between tests.
    from engine.log import context as ctx_mod

    ctx_mod._CONTEXT.set({})
    yield
    ctx_mod._CONTEXT.set({})


def _make_record(msg: str, extra: dict | None = None) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="sentinelqa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in (extra or {}).items():
        setattr(rec, k, v)
    return rec


def test_json_formatter_parses() -> None:
    record = _make_record("hello", {"run_id": "RUN-AAAAAAAAAAAA"})
    out = JSONFormatter().format(record)
    payload = json.loads(out)
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["extra"]["run_id"] == "RUN-AAAAAAAAAAAA"


def test_json_formatter_includes_context() -> None:
    token = LogContext.push({"run_id": "RUN-A"})
    try:
        record = _make_record("hi")
        out = JSONFormatter().format(record)
        payload = json.loads(out)
        assert payload["context"]["run_id"] == "RUN-A"
    finally:
        LogContext.pop(token)


def test_human_formatter_color_optional() -> None:
    record = _make_record("hello")
    plain = HumanFormatter(color=False).format(record)
    assert "\033[" not in plain
    color = HumanFormatter(color=True).format(record)
    assert "\033[" in color
