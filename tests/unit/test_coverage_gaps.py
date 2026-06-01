"""Coverage-gap tests for branches that the main suites don't already exercise.

requires ≥ 95% coverage on `engine/{domain,config,policy,errors,log}`.
This file holds the small set of tests needed to close the remaining lines
without bloating the topical test files.
"""

from __future__ import annotations

import json
import logging

from engine.errors.base import (
    ConfigSchemaError,
    DependencyMissingError,
    SentinelError,
    UnknownHostError,
)
from engine.errors.render import render_error
from engine.log import (
    LogContext,
    configure_logging,
    current_context,
    get_logger,
    log_context,
)
from engine.log.formatters import HumanFormatter
from engine.log.redaction_filter import RedactionFilter
from engine.policy.redaction import redact, redact_in_place
from engine.policy.safety import is_local

# ---------------------------------------------------------------------------
# redaction edge cases
# ---------------------------------------------------------------------------


def test_redact_depth_limit_marker() -> None:
    out = redact({"a": {"b": {"c": {"d": "deep"}}}}, depth=1)
    assert "[REDACTED:depth_limit]" in json.dumps(out)


def test_redact_opaque_object_falls_back_to_repr() -> None:
    class Opaque:
        def __repr__(self) -> str:
            return "<opaque sk-1234567890abcdef1234567890>"

    out = redact(Opaque())
    assert "sk-1234567890abcdef1234567890" not in str(out)


def test_redact_in_place_preserves_identity() -> None:
    payload = {"password": "hunter2", "ok": "yes"}
    original_id = id(payload)
    redact_in_place(payload)
    assert id(payload) == original_id
    assert payload["password"] == "[REDACTED:password]"


# ---------------------------------------------------------------------------
# safety helpers
# ---------------------------------------------------------------------------


def test_is_local_handles_unparseable() -> None:
    assert is_local("definitely-not-an-ip") is False


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def test_render_human_with_context_lines() -> None:
    err = UnknownHostError(host="evil.example.com", technical_context={"host": "evil.example.com"})
    out = render_error(err, mode="human")
    assert "Context:" in out


def test_render_human_verbose_no_traceback_safe() -> None:
    err = ConfigSchemaError(detail="boom")
    out = render_error(err, mode="human", verbose=True)
    assert "E-CFG-002" in out


def test_render_json_verbose_with_traceback() -> None:
    try:
        raise UnknownHostError(host="evil.example.com")
    except UnknownHostError as caught:
        out = render_error(caught, mode="json", verbose=True)
    payload = json.loads(out)
    assert "traceback" in payload


def test_render_error_dependency_missing_message_template() -> None:
    err = DependencyMissingError(dependency="playwright")
    assert "playwright" in err.message


# ---------------------------------------------------------------------------
# logging surface
# ---------------------------------------------------------------------------


def test_log_context_helper_pushes_and_pops() -> None:
    with log_context(run_id="RUN-X"):
        assert current_context()["run_id"] == "RUN-X"
    assert "run_id" not in current_context()


def test_get_logger_accepts_dotted_subname() -> None:
    log = get_logger("submodule")
    assert log.name == "sentinelqa.submodule"


def test_get_logger_passes_through_full_name() -> None:
    log = get_logger("sentinelqa.audit")
    assert log.name == "sentinelqa.audit"


def test_configure_logging_binds_run_id() -> None:
    configure_logging(mode="human", level="INFO", run_id="RUN-AAAAAAAAAAAA")
    assert current_context().get("run_id") == "RUN-AAAAAAAAAAAA"
    # Reset for hygiene.
    from engine.log import context as ctx_mod

    ctx_mod._CONTEXT.set({})
    logging.getLogger("sentinelqa").handlers.clear()


def test_human_formatter_renders_extras_and_context(capsys) -> None:
    token = LogContext.push({"run_id": "RUN-X"})
    try:
        record = logging.LogRecord(
            name="sentinelqa.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.user_field = "value"
        out = HumanFormatter(color=False).format(record)
        assert "user_field='value'" in out
        assert "run_id=RUN-X" in out
    finally:
        LogContext.pop(token)
    _ = capsys


def test_redaction_filter_handles_tuple_args() -> None:
    record = logging.LogRecord(
        name="sentinelqa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hi %s",
        args=("sk-abcdefghijklmnopqrstuvwxyz",),
        exc_info=None,
    )
    RedactionFilter().filter(record)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in str(record.args)


def test_redaction_filter_handles_dict_args() -> None:
    # LogRecord's constructor is finicky about dict args (Python issue #21172);
    # the realistic shape is to set them post-init, which the filter handles.
    record = logging.LogRecord(
        name="sentinelqa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hi %(t)s",
        args=None,
        exc_info=None,
    )
    record.args = {"t": "sk-abcdefghijklmnopqrstuvwxyz"}
    RedactionFilter().filter(record)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in str(record.args)


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


def test_sentinel_error_unknown_code_keeps_unspecified_message() -> None:
    err = SentinelError(code="E-UNREGISTERED-X")
    assert "Unspecified" in err.message


def test_sentinel_error_template_missing_field_falls_back() -> None:
    # E-CFG-001 expects {path}; omitting it falls back to the raw template
    # rather than crashing the formatter.
    err = SentinelError(code="E-CFG-001")
    assert "{path}" in err.message


# ---------------------------------------------------------------------------
# Safety policy edge cases
# ---------------------------------------------------------------------------


def test_normalize_host_strips_bracketed_ipv6_port() -> None:
    from engine.policy.safety import _normalize_host

    assert _normalize_host("[::1]:3000") == "::1"


def test_normalize_host_strips_ipv4_port() -> None:
    from engine.policy.safety import _normalize_host

    assert _normalize_host("localhost:3000") == "localhost"
    assert _normalize_host("example.com:notdigits") == "example.com:notdigits"


def test_safety_policy_rejects_url_without_host() -> None:
    """A URL with no hostname must trigger UnknownHostError.

    `file:///tmp/x` is the canonical example — urlparse returns ``hostname=None``,
    and SafetyPolicy's _extract_host turns that into a hard refusal.
    """

    import pytest
    from engine.errors.base import UnknownHostError
    from engine.policy.safety import SafetyPolicy

    with pytest.raises(UnknownHostError):
        SafetyPolicy()._extract_host("file:///tmp/x")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_read_audit_log_missing_file_returns_empty(tmp_path) -> None:
    from engine.policy.audit_log import read_audit_log

    assert read_audit_log(tmp_path / "nope.log") == []


def test_read_audit_log_skips_blank_lines(tmp_path) -> None:
    from engine.policy.audit_log import read_audit_log

    log = tmp_path / "audit.log"
    log.write_text('{"a": 1}\n\n   \n{"b": 2}\n')
    out = read_audit_log(log)
    assert out == [{"a": 1}, {"b": 2}]


# ---------------------------------------------------------------------------
# Render: human + verbose + color path
# ---------------------------------------------------------------------------


def test_render_human_verbose_with_color_includes_ansi() -> None:
    try:
        raise UnknownHostError(host="evil.example.com")
    except UnknownHostError as caught:
        out = render_error(caught, mode="human", verbose=True, color=True)
    assert "Traceback:" in out
    assert "\033[1;31m" in out


# ---------------------------------------------------------------------------
# Logging: quiet mode reaches handler path
# ---------------------------------------------------------------------------


def test_configure_logging_quiet_emits_error_only(capsys) -> None:
    configure_logging(mode="quiet")
    log = get_logger("test")
    log.info("ignored")
    log.error("kept")
    out = capsys.readouterr()
    assert "kept" in out.err
    assert "ignored" not in (out.out + out.err)
    logging.getLogger("sentinelqa").handlers.clear()


def test_json_formatter_includes_exc_info() -> None:
    from engine.log.formatters import JSONFormatter

    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="sentinelqa.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="x",
            args=(),
            exc_info=None,
        )
        import sys

        record.exc_info = sys.exc_info()
        out = JSONFormatter().format(record)
    payload = json.loads(out)
    assert payload["exc_type"] == "ValueError"
