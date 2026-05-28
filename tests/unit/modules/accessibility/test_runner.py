"""Unit tests for :mod:`modules.accessibility.runner`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from modules.accessibility.models import A11yPageResult, A11yRunOutcome
from modules.accessibility.runner import (
    A11yInvocation,
    A11yRunnerError,
    LocalA11yRunner,
    StubA11yRunner,
    _load_outcome,
)


def _config(tmp_path: Path) -> Any:
    from engine.config.loader import load_config

    p = tmp_path / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    return load_config(p)


def _safety_decision() -> Any:
    from datetime import UTC, datetime

    from engine.policy.safety import SafetyDecision

    return SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )


def _invocation(tmp_path: Path) -> A11yInvocation:
    return A11yInvocation(
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=tmp_path / "run",
        target="http://localhost:3000",
        routes=("/", "/dashboard"),
        axe_tags=("wcag2a", "wcag2aa"),
        request_timeout_seconds=30.0,
        keyboard_max_tabs=200,
    )


def test_stub_runner_records_invocation() -> None:
    page = A11yPageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        duration_ms=10,
    )
    runner = StubA11yRunner(pages=(page,))
    outcome = runner.run(
        A11yInvocation(
            run_id="RUN-AAAAAAAAAAAA",
            run_dir=Path("/tmp/run"),
            target="http://localhost:3000",
            routes=("/",),
            axe_tags=("wcag2a",),
            request_timeout_seconds=10.0,
            keyboard_max_tabs=50,
        )
    )
    assert outcome.pages == (page,)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/",)


def test_local_runner_raises_when_sentinel_ts_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SENTINEL_TS_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    runner = LocalA11yRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(A11yRunnerError, match="sentinel-ts"):
        runner.run(_invocation(tmp_path))


def test_local_runner_uses_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ts = tmp_path / "fake-ts.sh"
    fake_ts.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ts.chmod(0o755)
    monkeypatch.setenv("SENTINEL_TS_BIN", str(fake_ts))

    # subprocess.run should be invoked with our fake binary. We stub it to
    # avoid actually spawning a subprocess.
    captured: dict[str, list[str]] = {}

    def _fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        # Write a minimal index.json so the load path can proceed.
        run_dir = Path(argv[argv.index("--input") + 1]).parent
        (run_dir / "index.json").write_text(
            json.dumps({"pages": [], "incomplete": False}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = LocalA11yRunner(config=_config(tmp_path), safety=_safety_decision())
    outcome = runner.run(_invocation(tmp_path))
    assert outcome.pages == ()
    assert captured["argv"][0] == str(fake_ts)
    assert "audit-a11y" in captured["argv"]


def test_local_runner_propagates_subprocess_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ts = tmp_path / "fake-ts.sh"
    fake_ts.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ts.chmod(0o755)
    monkeypatch.setenv("SENTINEL_TS_BIN", str(fake_ts))

    def _fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 5, "", "Chromium launch failed")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = LocalA11yRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(A11yRunnerError, match="Chromium launch failed"):
        runner.run(_invocation(tmp_path))


def test_local_runner_protocol_violation_when_index_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ts = tmp_path / "fake-ts.sh"
    fake_ts.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ts.chmod(0o755)
    monkeypatch.setenv("SENTINEL_TS_BIN", str(fake_ts))

    def _fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, "", "")  # no index.json

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = LocalA11yRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(A11yRunnerError, match="protocol violation"):
        runner.run(_invocation(tmp_path))


def test_load_outcome_validates_payload(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    idx.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "route": "/",
                        "url": "http://localhost:3000/",
                        "fetched_at": "2026-05-28T00:00:00+00:00",
                        "duration_ms": 1,
                    }
                ],
                "incomplete": False,
            }
        ),
        encoding="utf-8",
    )
    outcome = _load_outcome(idx, duration_ms=99)
    assert isinstance(outcome, A11yRunOutcome)
    assert outcome.duration_ms == 99
    assert outcome.pages[0].route == "/"


def test_load_outcome_rejects_bad_shape(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    idx.write_text("[]", encoding="utf-8")
    with pytest.raises(A11yRunnerError, match="malformed"):
        _load_outcome(idx, duration_ms=0)
