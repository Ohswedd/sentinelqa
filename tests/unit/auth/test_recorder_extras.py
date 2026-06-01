# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Extra coverage for the auth recorder edge paths."""

from __future__ import annotations

from engine.auth.recorder import (
    RecordedSession,
    parse_assertion_response,
    parse_codegen_transcript,
)


def test_parse_codegen_transcript_handles_invalid_json_lines() -> None:
    blob = '{"action":"click"\n{"action":"click","selector":"a"}\n'
    session = parse_codegen_transcript(blob, start_url="https://x")
    assert len(session.steps) == 1


def test_parse_codegen_transcript_records_goto_url() -> None:
    blob = '{"action":"goto","url":"https://app.example.com/dash"}\n'
    session = parse_codegen_transcript(blob, start_url="https://app.example.com/login")
    assert session.final_url == "https://app.example.com/dash"


def test_parse_assertion_response_returns_empty_when_not_array() -> None:
    assert parse_assertion_response('{"kind": "selector"}') == ()


def test_parse_assertion_response_returns_empty_when_invalid_json() -> None:
    assert parse_assertion_response("not json") == ()


def test_parse_assertion_response_drops_rows_missing_value() -> None:
    raw = '[{"kind": "selector"}, {"kind": "selector", "value": "  "}]'
    assert parse_assertion_response(raw) == ()


def test_recorded_session_is_frozen() -> None:
    session = RecordedSession(start_url="https://x", steps=())
    try:
        session.start_url = "y"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("RecordedSession should be frozen")
