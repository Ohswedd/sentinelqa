"""Helper coverage for :mod:`engine.runner.local` and :mod:`engine.runner.docker`."""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import (
    AuthConfig,
    ModulesConfig,
    ProjectConfig,
    RootConfig,
    RunnerConfig,
    SourceConfig,
    TargetConfig,
)
from engine.runner.local import (
    LocalRunner,
    RunnerSpawnError,
    _collect_environment,
    _drain_stream,
    _relative_or_absolute,
    _resolve_workers,
    _safe_await_bytes,
    _terminate,
    _write_runner_log,
)


def _config(tmp_path: Path) -> RootConfig:
    return RootConfig(
        version=1,
        project=ProjectConfig(name="t"),
        source=SourceConfig(root=tmp_path),
        target=TargetConfig(base_url="http://localhost"),
        auth=AuthConfig(),
        modules=ModulesConfig(),
        runner=RunnerConfig(),
    )


def test_resolve_workers_auto_falls_back_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: None)
    assert _resolve_workers("auto") == 1


def test_resolve_workers_auto_uses_cpu_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    assert _resolve_workers("auto") == 8


def test_resolve_workers_integer_is_passed_through() -> None:
    assert _resolve_workers(4) == 4


def test_collect_environment_reads_node_and_playwright_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NODE_VERSION", "20.17.0")
    monkeypatch.setenv("PLAYWRIGHT_VERSION", "1.49.0")
    env = _collect_environment(_config(tmp_path))
    assert env.node_version == "20.17.0"
    assert env.playwright_version == "1.49.0"


def test_relative_or_absolute_inside_run_dir(tmp_path: Path) -> None:
    spec = tmp_path / "tests" / "sentinel" / "x.spec.ts"
    spec.parent.mkdir(parents=True)
    spec.write_text("", encoding="utf-8")
    assert _relative_or_absolute(spec, tmp_path) == "tests/sentinel/x.spec.ts"


def test_relative_or_absolute_outside_run_dir(tmp_path: Path) -> None:
    other = Path("/etc/hosts")  # canonical absolute path
    assert _relative_or_absolute(other, tmp_path).startswith("/")


def test_resolve_sentinel_ts_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_TS_BIN", "/opt/sentinel-ts")
    runner = LocalRunner(config=_config(tmp_path))
    assert runner._resolve_sentinel_ts() == "/opt/sentinel-ts"


def test_resolve_sentinel_ts_uses_shutil_which(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SENTINEL_TS_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/sentinel-ts")
    runner = LocalRunner(config=_config(tmp_path))
    assert runner._resolve_sentinel_ts() == "/usr/bin/sentinel-ts"


def test_drain_stream_handles_none() -> None:
    out = asyncio.run(_drain_stream(None))
    assert out == b""


def test_safe_await_bytes_swallows_cancelled() -> None:
    async def _driver() -> bytes:
        task: asyncio.Task[bytes] = asyncio.create_task(asyncio.sleep(60, result=b"x"))
        task.cancel()
        return await _safe_await_bytes(task)

    assert asyncio.run(_driver()) == b""


def test_safe_await_bytes_swallows_arbitrary_exception() -> None:
    async def _boom() -> bytes:
        raise RuntimeError("nope")

    async def _driver() -> bytes:
        task: asyncio.Task[bytes] = asyncio.create_task(_boom())
        return await _safe_await_bytes(task)

    assert asyncio.run(_driver()) == b""


def test_write_runner_log_redacts(tmp_path: Path) -> None:
    log_path = tmp_path / "runner.log"
    secret = b"Authorization: Bearer sk-12345secretvalue\n"
    _write_runner_log(log_path, secret, exit_code=1)
    body = log_path.read_text(encoding="utf-8")
    assert "exit_code=1" in body
    assert "sk-12345secretvalue" not in body


class _AlreadyDone:
    def __init__(self) -> None:
        self.signals: list[int] = []
        self.terminated = False
        self.killed = False
        self._rc = 0

    @property
    def returncode(self) -> int | None:
        return self._rc

    def send_signal(self, sig: int) -> None:  # pragma: no cover - unused
        self.signals.append(sig)

    def terminate(self) -> None:  # pragma: no cover - unused
        self.terminated = True

    def kill(self) -> None:  # pragma: no cover - unused
        self.killed = True

    async def wait(self) -> int:
        return self._rc


def test_terminate_noop_when_already_exited() -> None:
    proc: Any = _AlreadyDone()
    asyncio.run(_terminate(proc, grace=0.01))
    assert proc.signals == []


class _NeverDies:
    """Process that ignores every signal — exercises the SIGKILL fallback."""

    def __init__(self) -> None:
        self.signals: list[int] = []
        self.terminated = False
        self.killed = False
        self._rc: int | None = None

    @property
    def returncode(self) -> int | None:
        return self._rc

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True
        self._rc = -9

    async def wait(self) -> int:
        # Never resolves until kill flips the rc.
        while self._rc is None:
            await asyncio.sleep(0.005)
        return self._rc


def test_terminate_escalates_to_sigkill() -> None:
    proc: Any = _NeverDies()
    asyncio.run(_terminate(proc, grace=0.01))
    assert signal.SIGINT in proc.signals
    assert proc.terminated is True
    assert proc.killed is True


def test_local_runner_spawn_raises_runner_spawn_error_on_os_error(
    tmp_path: Path,
) -> None:
    async def _fail_spawn(*_args: Any, **_kw: Any) -> Any:
        raise OSError("no such binary")

    runner = LocalRunner(
        config=_config(tmp_path),
        sentinel_ts_path="/nonexistent/sentinel-ts",
        spawn_fn=_fail_spawn,
    )
    from engine.runner.local import RunnerInvocation

    with pytest.raises(RunnerSpawnError):
        runner.run(
            RunnerInvocation(
                run_id="RUN-OSAAAAAAAAA",
                run_dir=tmp_path,
                target="http://localhost",
                module_name="functional",
                spec_files=[Path("a.spec.ts")],
            )
        )
