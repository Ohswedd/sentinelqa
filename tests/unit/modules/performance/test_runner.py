"""Unit tests for :mod:`modules.performance.runner`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from modules.performance.models import (
    PerformancePageResult,
    PerformanceRunOutcome,
)
from modules.performance.runner import (
    LocalPerformanceRunner,
    PerformanceInvocation,
    PerformanceRunnerError,
    StubPerformanceRunner,
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


def _invocation(tmp_path: Path) -> PerformanceInvocation:
    return PerformanceInvocation(
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=tmp_path / "run",
        target="http://localhost:3000",
        routes=("/", "/dashboard"),
        samples=3,
        repeated_nav_samples=5,
        request_timeout_seconds=30.0,
        api_path_allowlist=("/api/",),
    )


def test_stub_runner_records_invocation() -> None:
    page = PerformancePageResult(
        route="/",
        url="http://localhost:3000/",
        fetched_at="2026-05-28T00:00:00+00:00",
        duration_ms=10,
    )
    runner = StubPerformanceRunner(pages=(page,))
    outcome = runner.run(
        PerformanceInvocation(
            run_id="RUN-AAAAAAAAAAAA",
            run_dir=Path("/tmp/run"),
            target="http://localhost:3000",
            routes=("/",),
            samples=3,
            repeated_nav_samples=5,
            request_timeout_seconds=10.0,
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
    runner = LocalPerformanceRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(PerformanceRunnerError, match="sentinel-ts"):
        runner.run(_invocation(tmp_path))


def test_local_runner_uses_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ts = tmp_path / "fake-ts.sh"
    fake_ts.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ts.chmod(0o755)
    monkeypatch.setenv("SENTINEL_TS_BIN", str(fake_ts))

    captured: dict[str, list[str]] = {}

    def _fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        run_dir = Path(argv[argv.index("--input") + 1]).parent
        (run_dir / "index.json").write_text(
            json.dumps({"pages": [], "incomplete": False}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = LocalPerformanceRunner(config=_config(tmp_path), safety=_safety_decision())
    outcome = runner.run(_invocation(tmp_path))
    assert outcome.pages == ()
    assert captured["argv"][0] == str(fake_ts)
    assert "audit-perf" in captured["argv"]


def test_local_runner_falls_back_to_shutil_which(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SENTINEL_TS_BIN", raising=False)
    fake_ts = tmp_path / "fake-ts.sh"
    fake_ts.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ts.chmod(0o755)
    monkeypatch.setattr(
        "shutil.which", lambda name: str(fake_ts) if name == "sentinel-ts" else None
    )

    def _fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        run_dir = Path(argv[argv.index("--input") + 1]).parent
        (run_dir / "index.json").write_text(
            json.dumps({"pages": [], "incomplete": False}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    runner = LocalPerformanceRunner(config=_config(tmp_path), safety=_safety_decision())
    runner.run(_invocation(tmp_path))


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
    runner = LocalPerformanceRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(PerformanceRunnerError, match="Chromium launch failed"):
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
    runner = LocalPerformanceRunner(config=_config(tmp_path), safety=_safety_decision())
    with pytest.raises(PerformanceRunnerError, match="protocol violation"):
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
    assert isinstance(outcome, PerformanceRunOutcome)
    assert outcome.duration_ms == 99
    assert outcome.pages[0].route == "/"


def test_load_outcome_rejects_non_object(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    idx.write_text("[]", encoding="utf-8")
    with pytest.raises(PerformanceRunnerError, match="malformed"):
        _load_outcome(idx, duration_ms=0)


def test_load_outcome_rejects_non_list_pages(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"pages": "not a list"}), encoding="utf-8")
    with pytest.raises(PerformanceRunnerError, match="must be a list"):
        _load_outcome(idx, duration_ms=0)
