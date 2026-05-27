"""Logging-mode behaviour tests (CLAUDE.md §13)."""

from __future__ import annotations

import json
import logging

import pytest
from engine.log import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset() -> None:
    yield
    # Clean up handlers between tests so modes don't leak.
    logging.getLogger("sentinelqa").handlers.clear()


def test_json_mode_emits_json_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    # CLAUDE §13: in JSON mode stdout is reserved for the CLI's
    # machine-readable payload. All log records (including INFO) go to
    # stderr so piping stdout through `jq` stays clean.
    configure_logging(mode="json", level="INFO")
    log = get_logger("test")
    log.info("hello")
    captured = capsys.readouterr()
    assert captured.out == "", "JSON mode must not write logs to stdout."
    line = captured.err.strip()
    assert line, "JSON mode should write log records to stderr."
    payload = json.loads(line)
    assert payload["msg"] == "hello"


def test_quiet_mode_silences_info(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(mode="quiet", level="INFO")
    log = get_logger("test")
    log.info("noise")
    log.error("boom")
    out = capsys.readouterr()
    assert "noise" not in (out.out + out.err)
    assert "boom" in (out.out + out.err)


def test_human_mode_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(mode="human", level="INFO")
    log = get_logger("test")
    log.info("howdy")
    out = capsys.readouterr()
    assert "howdy" in out.err
    assert "howdy" not in out.out
