"""RedactionFilter tests — secrets must not reach a stream."""

from __future__ import annotations

import logging

from engine.log.redaction_filter import RedactionFilter


def _record(msg: str, **extras) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="sentinelqa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extras.items():
        setattr(rec, k, v)
    return rec


def test_msg_redacted() -> None:
    record = _record("Authorization: Bearer abc.def.ghi")
    RedactionFilter().filter(record)
    assert "Bearer abc.def.ghi" not in record.msg


def test_extras_redacted() -> None:
    record = _record("ok", token="sk-1234567890abcdef1234567890")
    RedactionFilter().filter(record)
    assert "sk-" not in str(getattr(record, "token", ""))


def test_builtin_fields_untouched() -> None:
    record = _record("ok")
    pathname_before = record.pathname
    RedactionFilter().filter(record)
    assert record.pathname == pathname_before
