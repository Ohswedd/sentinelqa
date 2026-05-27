"""Targeted coverage for CLI paths not exercised by integration tests."""

from __future__ import annotations

import json
import sys

import pytest
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
)

from sentinel_cli import main as main_mod
from sentinel_cli.json_mode import _GuardedTextIO, json_stdout
from sentinel_cli.state import GlobalState

# ---------------------------------------------------------------------------
# json_mode
# ---------------------------------------------------------------------------


def test_guarded_textio_accepts_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINELQA_ASSERT_JSON_STDOUT", "1")
    with json_stdout() as out:
        out.emit({"k": "v"})
        # Manual JSON line written directly should also pass the guard.
        sys.stdout.write('{"manual":true}\n')


def test_guarded_textio_trailing_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINELQA_ASSERT_JSON_STDOUT", "1")
    with json_stdout() as out:
        out.emit({"first": 1})


def test_guarded_textio_trailing_invalid_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINELQA_ASSERT_JSON_STDOUT", "1")
    with pytest.raises(AssertionError), json_stdout() as out:
        out.emit({"a": 1})
        sys.stdout.write("partial-without-newline-not-json")


def test_guarded_textio_flush_and_isatty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded = _GuardedTextIO(sys.stdout)
    # flush + isatty cover the small surface methods.
    guarded.flush()
    assert guarded.isatty() is False
    # Empty trailing buffer must unwrap cleanly.
    assert guarded.unwrap() is sys.stdout


def test_emit_helper_wraps_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    from sentinel_cli.json_mode import emit

    with json_stdout() as out:
        emit(out, {"hello": "world"})


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------


def test_global_state_log_level_paths() -> None:
    assert GlobalState().log_level == "INFO"
    assert GlobalState(verbose=True).log_level == "DEBUG"
    assert GlobalState(quiet=True).log_level == "ERROR"


def test_global_state_mode_precedence() -> None:
    assert GlobalState().mode == "human"
    assert GlobalState(verbose=True).mode == "human"
    assert GlobalState(ci=True, quiet=True).mode == "quiet"


# ---------------------------------------------------------------------------
# main entry point error paths
# ---------------------------------------------------------------------------


def test_main_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raises(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt()

    monkeypatch.setattr(main_mod, "app", raises)
    code = main_mod.main([])
    assert code == EXIT_INTERNAL_ERROR


def test_main_handles_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raises(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main_mod, "app", raises)
    code = main_mod.main([])
    assert code == EXIT_INTERNAL_ERROR


def test_main_handles_sentinel_error_in_human_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from engine.errors.base import ConfigFileNotFoundError

    def raises(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConfigFileNotFoundError(path="/nope")

    monkeypatch.setattr(main_mod, "app", raises)
    code = main_mod.main([])
    assert code == EXIT_CONFIG_ERROR
    captured = capsys.readouterr()
    assert "E-CFG-001" in captured.err


def test_main_handles_sentinel_error_in_json_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from engine.errors.base import ConfigFileNotFoundError

    def raises(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConfigFileNotFoundError(path="/nope")

    monkeypatch.setattr(main_mod, "app", raises)
    code = main_mod.main(["--json"])
    assert code == EXIT_CONFIG_ERROR
    captured = capsys.readouterr()
    # JSON payload on stdout.
    payload = json.loads(captured.out.strip())
    assert payload["code"] == "E-CFG-001"


def test_main_usage_error_returns_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unknown flag triggers click.UsageError.
    code = main_mod.main(["--definitely-not-a-flag"])
    assert code == EXIT_CONFIG_ERROR
