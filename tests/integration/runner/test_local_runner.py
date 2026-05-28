"""Integration tests for :class:`LocalRunner` (08.01).

The runner is exercised end-to-end without spawning a real
``sentinel-ts`` subprocess: we inject a fake ``spawn_fn`` that returns
an in-memory :class:`asyncio.subprocess.Process` whose stdout / stderr
streams emit predetermined bytes. This proves the bridge:

  spawn → stdout JSONL → parser → aggregator → ModuleResult

without requiring Playwright or Chromium to be installed.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import (
    AuthConfig,
    ModulesConfig,
    PerformanceBudgets,
    PerformanceConfig,
    ProjectConfig,
    RootConfig,
    RunnerConfig,
    RunnerQuarantineConfig,
    RunnerRetriesConfig,
    TargetConfig,
)
from engine.runner.local import (
    LocalRunner,
    RunnerInvocation,
    RunnerSpawnError,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeReader:
    """Minimal async iterator yielding JSONL lines."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def __aiter__(self) -> _FakeReader:
        return self

    async def __anext__(self) -> bytes:
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)

    async def read(self, _n: int) -> bytes:  # for _drain_stream
        if not self._lines:
            return b""
        chunk = b"".join(self._lines)
        self._lines.clear()
        return chunk


class _FakeProcess:
    def __init__(
        self,
        stdout_lines: list[bytes],
        stderr_bytes: bytes = b"",
        returncode: int = 0,
    ) -> None:
        self.stdout = _FakeReader(stdout_lines)
        self.stderr = _FakeReader([stderr_bytes] if stderr_bytes else [])
        self._returncode = returncode

    @property
    def returncode(self) -> int | None:
        return self._returncode

    async def wait(self) -> int:
        return self._returncode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_config(tmp_path: Path) -> RootConfig:
    return RootConfig(
        version=1,
        project=ProjectConfig(name="phase-08-test"),
        target=TargetConfig(base_url="http://localhost"),
        auth=AuthConfig(),
        modules=ModulesConfig(),
        performance=PerformanceConfig(budgets=PerformanceBudgets()),
        runner=RunnerConfig(
            workers=1,
            browser="chromium",
            headless=True,
            timeout_ms=10_000,
            retries=RunnerRetriesConfig(max=1, backoff_ms=500),
            quarantine=RunnerQuarantineConfig(path=tmp_path / "quarantine.yaml"),
        ),
    )


def _event(**fields: object) -> bytes:
    payload = {
        "schema_version": "1.0.0",
        "seq": fields.pop("seq", 1),
        "ts": "2026-05-28T12:00:00+00:00",
        **fields,
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


def _full_jsonl() -> list[bytes]:
    return [
        _event(
            type="run.start",
            run_id="RUN-FAKE",
            target="http://localhost",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(type="test.start", test_id="t1", title="login passes", file="login.spec.ts", seq=2),
        _event(type="test.end", test_id="t1", duration_ms=400, status="passed", retries=0, seq=3),
        _event(
            type="run.end",
            run_id="RUN-FAKE",
            finished_at="2026-05-28T12:00:01+00:00",
            status="passed",
            tests_total=1,
            tests_failed=0,
            seq=4,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_local_runner_streams_jsonl_into_module_result(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    spawned: dict[str, Any] = {}

    async def fake_spawn(*args: Any, **kwargs: Any) -> _FakeProcess:
        spawned["cmd"] = args[0]
        spawned["args"] = args[1:]
        return _FakeProcess(_full_jsonl(), stderr_bytes=b"", returncode=0)

    runner = LocalRunner(
        config=config,
        sentinel_ts_path="/usr/local/bin/sentinel-ts",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-LOCALAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[Path("tests/sentinel/login.spec.ts")],
    )

    outcome = runner.run(invocation)

    assert outcome.module_result.status == "passed"
    assert outcome.module_result.metrics["tests_total"] == 1
    assert outcome.module_result.metrics["tests_passed"] == 1
    assert outcome.tests[0].test_id == "t1"

    # The run-config was persisted under the run dir.
    cfg_path = tmp_path / "run-configs" / "functional.json"
    assert cfg_path.exists()
    cfg_payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg_payload["target"] == "http://localhost"
    assert cfg_payload["browser"] == "chromium"
    assert len(cfg_payload["spec_files"]) == 1
    assert cfg_payload["spec_files"][0].endswith("login.spec.ts")

    # The module-results artifact landed where Phase 14 will look.
    module_results_path = tmp_path / "module-results" / "functional.json"
    assert module_results_path.exists()

    # The runner log was written even on a successful run.
    log_path = tmp_path / "logs" / "runner.functional.log"
    assert log_path.exists()
    assert "exit_code=0" in log_path.read_text(encoding="utf-8")

    assert spawned["cmd"] == "/usr/local/bin/sentinel-ts"
    assert spawned["args"][0] == "run"
    assert spawned["args"][1] == "--input"


def test_local_runner_handles_partial_stream(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    lines = _full_jsonl()[:-1]  # drop run.end

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _FakeProcess:
        return _FakeProcess(lines, stderr_bytes=b"playwright crashed", returncode=2)

    runner = LocalRunner(
        config=config,
        sentinel_ts_path="/usr/bin/sentinel-ts",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-PARTAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[Path("login.spec.ts")],
    )
    outcome = runner.run(invocation)

    assert outcome.module_result.status == "incomplete"
    assert outcome.incomplete is True
    # Runner log records the failing exit code and the captured stderr.
    log_path = tmp_path / "logs" / "runner.functional.log"
    assert "exit_code=2" in log_path.read_text(encoding="utf-8")
    assert "playwright crashed" in log_path.read_text(encoding="utf-8")


def test_local_runner_redacts_stderr_log(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    secret_line = b"Authorization: Bearer sk-thisissupersecret123\n"

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _FakeProcess:
        return _FakeProcess(_full_jsonl(), stderr_bytes=secret_line, returncode=0)

    runner = LocalRunner(
        config=config, sentinel_ts_path="/usr/bin/sentinel-ts", spawn_fn=fake_spawn
    )
    invocation = RunnerInvocation(
        run_id="RUN-SECRAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[Path("any.spec.ts")],
    )
    runner.run(invocation)

    log_text = (tmp_path / "logs" / "runner.functional.log").read_text(encoding="utf-8")
    # The actual secret value MUST not appear verbatim.
    assert "sk-thisissupersecret123" not in log_text


def test_local_runner_raises_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path)
    monkeypatch.delenv("SENTINEL_TS_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)

    runner = LocalRunner(config=config)
    invocation = RunnerInvocation(
        run_id="RUN-MISSAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[Path("any.spec.ts")],
    )
    with pytest.raises(RunnerSpawnError):
        runner.run(invocation)


def test_local_runner_writes_shard_into_run_config(tmp_path: Path) -> None:
    config = _build_config(tmp_path)

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _FakeProcess:
        return _FakeProcess(_full_jsonl())

    runner = LocalRunner(
        config=config, sentinel_ts_path="/usr/bin/sentinel-ts", spawn_fn=fake_spawn
    )
    invocation = RunnerInvocation(
        run_id="RUN-SHARDAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[Path("any.spec.ts")],
        shard=__import__("engine.runner.sharding", fromlist=["ShardSpec"]).ShardSpec(
            current=2, total=4
        ),
        workers=3,
    )
    runner.run(invocation)
    cfg = json.loads((tmp_path / "run-configs" / "functional.json").read_text(encoding="utf-8"))
    assert cfg["shard"] == {"current": 2, "total": 4}
    assert cfg["workers"] == 3


# ---------------------------------------------------------------------------
# SIGINT propagation
# ---------------------------------------------------------------------------


class _SlowReader:
    """Reader that never emits — used to force a cancellation path."""

    def __aiter__(self) -> _SlowReader:
        return self

    async def __anext__(self) -> bytes:
        await asyncio.sleep(60)
        raise StopAsyncIteration

    async def read(self, _n: int) -> bytes:
        await asyncio.sleep(60)
        return b""


class _TrackingProcess:
    def __init__(self) -> None:
        self.stdout = _SlowReader()
        self.stderr = _SlowReader()
        self._returncode: int | None = None
        self.signals: list[int] = []
        self.terminated = False
        self.killed = False

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)
        self._returncode = -sig

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = -15

    def kill(self) -> None:  # pragma: no cover — defensive
        self.killed = True
        self._returncode = -9

    async def wait(self) -> int:
        # Resolve immediately once a signal has been recorded.
        return self._returncode or 0


def test_local_runner_propagates_cancellation(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    tracker = _TrackingProcess()

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _TrackingProcess:
        return tracker

    runner = LocalRunner(
        config=config,
        sentinel_ts_path="/usr/bin/sentinel-ts",
        spawn_fn=fake_spawn,  # type: ignore[arg-type]
        shutdown_grace_seconds=0.01,
    )

    async def _driver() -> None:
        invocation = RunnerInvocation(
            run_id="RUN-CANCEAAAAAAA",
            run_dir=tmp_path,
            target="http://localhost",
            module_name="functional",
            spec_files=[Path("any.spec.ts")],
        )
        task = asyncio.create_task(runner.run_async(invocation))
        # Give the runner a tick to start, then cancel.
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(_driver())

    import signal

    assert signal.SIGINT in tracker.signals
