"""Local Playwright runner (Phase 08.01).

The :class:`LocalRunner` spawns ``sentinel-ts run --input <path>`` as a
subprocess, streams stdout JSONL through the Phase-04 bridge into the
Phase-08.05 aggregator, and returns a typed :class:`RunnerOutcome`.

Design choices:

- **Subprocess via** :func:`asyncio.create_subprocess_exec` so we can
  consume stdout line-by-line without blocking. The implementation is
  also synchronous-callable through :meth:`LocalRunner.run` which wraps
  the coroutine in :func:`asyncio.run`.
- **Stderr is captured fully** and forwarded — after redaction — to
  ``<run-dir>/logs/runner.log`` regardless of exit code, so failure
  triage has the underlying Playwright noise. The audit log captures
  ``runner.complete`` with exit code + duration; the log file path is
  what users open.
- **SIGINT propagation:** when the parent receives SIGINT (or the
  caller cancels the coroutine), we forward SIGINT to the child and
  wait up to ``shutdown_grace_seconds`` before SIGTERM, then SIGKILL.
- **Safety:** :meth:`LocalRunner.run` is a no-op call; the caller is
  expected to have already enforced :class:`engine.policy.safety.SafetyPolicy`
  via the lifecycle. The Docker runner repeats the check before
  spawning a container because container launch crosses a more
  expensive boundary.
- **Determinism:** every invocation gets a fresh ``run-config.json``
  file under the run dir (`run-config/<module>.json`); the file is
  committed to disk before the child is spawned so post-mortem
  reproduction is possible.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import platform
import shutil
import signal
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.config.schema import RootConfig
from engine.domain.ids import IdGenerator
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.ts_bridge import (
    ProtocolParseError,
    parse_event,
    stream_events,
)
from engine.policy.redaction import redact
from engine.runner.quarantine import Quarantine
from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    aggregate,
    write_module_results,
)
from engine.runner.run_config import RunConfig, ShardConfig
from engine.runner.sharding import ShardSpec

DEFAULT_SHUTDOWN_GRACE_SECONDS = 5.0


class LocalRunnerError(RuntimeError):
    """Raised when the local runner cannot complete its work."""


class RunnerSpawnError(LocalRunnerError):
    """Raised when the runner cannot locate or spawn ``sentinel-ts``."""


@dataclass(frozen=True)
class RunnerInvocation:
    """Inputs the runner needs from the caller (replaces a long kwargs list)."""

    run_id: str
    run_dir: Path
    target: str
    module_name: str
    spec_files: Sequence[Path]
    shard: ShardSpec | None = None
    workers: int | None = None
    quarantine: Quarantine = field(default_factory=Quarantine.empty)


SpawnFn = Callable[..., Awaitable[asyncio.subprocess.Process]]


class LocalRunner:
    """Spawn ``sentinel-ts run`` locally and return a :class:`RunnerOutcome`.

    The runner is stateless across invocations — every call writes its
    own ``run-config.json`` and reads stdout to completion.
    """

    def __init__(
        self,
        *,
        config: RootConfig,
        sentinel_ts_path: str | None = None,
        spawn_fn: SpawnFn | None = None,
        shutdown_grace_seconds: float = DEFAULT_SHUTDOWN_GRACE_SECONDS,
        id_generator: IdGenerator | None = None,
        env_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        self._sentinel_ts_path = sentinel_ts_path
        self._spawn_fn: SpawnFn = spawn_fn or asyncio.create_subprocess_exec
        self._grace = shutdown_grace_seconds
        self._ids = id_generator or IdGenerator()
        self._env_overrides = dict(env_overrides or {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:
        """Synchronous entry point. Wraps :meth:`run_async` in ``asyncio.run``."""

        return asyncio.run(self.run_async(invocation))

    async def run_async(self, invocation: RunnerInvocation) -> RunnerOutcome:
        run_dir = invocation.run_dir
        artifacts = ArtifactDirectory(run_dir)
        config_path = self._write_run_config(artifacts, invocation)
        cmd, args = self._build_command(config_path)

        logs_dir = artifacts.subdir("logs")
        runner_log_path = logs_dir / f"runner.{invocation.module_name}.log"

        proc = await self._spawn(cmd, args)
        outcome = await self._consume(
            proc=proc,
            invocation=invocation,
            runner_log_path=runner_log_path,
        )
        write_module_results(artifacts, outcome)
        return outcome

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_sentinel_ts(self) -> str:
        if self._sentinel_ts_path is not None:
            return self._sentinel_ts_path
        env_path = os.environ.get("SENTINEL_TS_BIN")
        if env_path:
            return env_path
        on_path = shutil.which("sentinel-ts")
        if on_path is not None:
            return on_path
        raise RunnerSpawnError(
            "sentinel-ts binary not found. Set SENTINEL_TS_BIN, "
            "pass sentinel_ts_path=, or run "
            "`pnpm --filter @sentinelqa/ts-runtime build` then "
            "`pnpm link --global` so the binary is on PATH."
        )

    def _build_command(self, config_path: Path) -> tuple[str, list[str]]:
        bin_path = self._resolve_sentinel_ts()
        return bin_path, ["run", "--input", str(config_path)]

    def _write_run_config(
        self,
        artifacts: ArtifactDirectory,
        invocation: RunnerInvocation,
    ) -> Path:
        runner_cfg = self._config.runner
        workers = (
            invocation.workers
            if invocation.workers is not None
            else _resolve_workers(runner_cfg.workers)
        )
        shard = invocation.shard or (
            ShardSpec.parse(runner_cfg.shards) if runner_cfg.shards else None
        )
        spec_files = tuple(
            _relative_or_absolute(p, invocation.run_dir) for p in invocation.spec_files
        )

        env: dict[str, str] = dict(self._env_overrides)
        env.setdefault("SENTINELQA_RUN_ID", invocation.run_id)
        env.setdefault("SENTINELQA_RUN_DIR", str(invocation.run_dir))

        run_config = RunConfig(
            run_id=invocation.run_id,
            target=invocation.target,
            run_dir=str(invocation.run_dir),
            spec_files=spec_files,
            workers=workers,
            shard=ShardConfig(current=shard.current, total=shard.total) if shard else None,
            browser=runner_cfg.browser,
            headless=runner_cfg.headless,
            timeout_ms=runner_cfg.timeout_ms,
            retries=runner_cfg.retries.max,
            env=env,
        )
        # Persist under run-configs/<module>.json so each module's invocation
        # is independently reproducible.
        out_dir = artifacts.subdir("run-configs")
        target = out_dir / f"{invocation.module_name}.json"
        target.write_text(
            json.dumps(run_config.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    async def _spawn(self, cmd: str, args: Sequence[str]) -> asyncio.subprocess.Process:
        try:
            return await self._spawn_fn(
                cmd,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise RunnerSpawnError(f"failed to spawn sentinel-ts ({cmd!r}): {exc}") from exc

    async def _consume(
        self,
        *,
        proc: asyncio.subprocess.Process,
        invocation: RunnerInvocation,
        runner_log_path: Path,
    ) -> RunnerOutcome:
        module_id = self._ids.new("MOD")
        # Collect stderr concurrently so we don't deadlock on a full pipe.
        stderr_task = asyncio.create_task(_drain_stream(proc.stderr))
        cancelled = False

        try:
            assert proc.stdout is not None
            events_iter = _stream_or_partial(proc.stdout)
            outcome = await aggregate(
                events_iter,
                module_name=invocation.module_name,
                module_id=module_id,
                environment=_collect_environment(self._config),
                quarantined_test_ids=invocation.quarantine.test_ids(),
            )
        except asyncio.CancelledError:
            cancelled = True
            await _terminate(proc, grace=self._grace)
            raise
        finally:
            if cancelled:
                stderr_task.cancel()
            stderr_bytes = await _safe_await_bytes(stderr_task)
            with contextlib.suppress(asyncio.TimeoutError, ProcessLookupError):
                await asyncio.wait_for(proc.wait(), timeout=self._grace)
            _write_runner_log(runner_log_path, stderr_bytes, exit_code=proc.returncode)

        return outcome


# ---------------------------------------------------------------------------
# Helpers shared with the Docker runner
# ---------------------------------------------------------------------------


def _resolve_workers(value: int | str) -> int:
    if value == "auto":
        return max(os.cpu_count() or 1, 1)
    return int(value)


def _relative_or_absolute(path: Path, run_dir: Path) -> str:
    """Prefer a POSIX-relative path; fall back to absolute when impossible."""

    try:
        return path.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _collect_environment(config: RootConfig) -> EnvironmentContext:
    return EnvironmentContext(
        browser=config.runner.browser,
        browser_version="bundled",  # Playwright bundles browsers.
        os=f"{platform.system()}-{platform.release()}",
        node_version=os.environ.get("NODE_VERSION"),
        playwright_version=os.environ.get("PLAYWRIGHT_VERSION"),
    )


async def _drain_stream(stream: asyncio.StreamReader | None) -> bytes:
    if stream is None:
        return b""
    chunks: list[bytes] = []
    try:
        while True:
            chunk = await stream.read(64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    except asyncio.CancelledError:
        return b"".join(chunks)
    return b"".join(chunks)


async def _safe_await_bytes(task: asyncio.Task[bytes]) -> bytes:
    """Await a stderr-collection task, returning ``b""`` on cancel/error."""

    try:
        return await task
    except (asyncio.CancelledError, Exception):
        return b""


async def _terminate(proc: asyncio.subprocess.Process, *, grace: float) -> None:
    """Try SIGINT → SIGTERM → SIGKILL, honoring ``grace`` seconds per step."""

    if proc.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        if sys.platform == "win32":  # pragma: no cover — Unix-only test surface
            proc.terminate()
        else:
            proc.send_signal(signal.SIGINT)
    try:
        await asyncio.wait_for(proc.wait(), timeout=grace)
        return
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=grace)
        return
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    await proc.wait()


async def _stream_or_partial(reader: asyncio.StreamReader) -> Any:
    """Yield typed events from ``reader`` with malformed lines treated as gaps.

    Unlike :func:`engine.orchestrator.ts_bridge.stream_events`, this
    iterator does NOT raise :class:`ProtocolParseError`: a partial / racy
    JSON line is a sign of an interrupted run, not a contract violation.
    The aggregator surfaces that as ``status='incomplete'``.
    """

    async for raw in reader:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if not text.strip():
            continue
        try:
            yield parse_event(text)
        except ProtocolParseError:
            continue


def _write_runner_log(path: Path, stderr: bytes, *, exit_code: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = stderr.decode("utf-8", errors="replace")
    redacted = redact(text) if isinstance(text, str) else text
    header = f"# sentinel-ts exit_code={exit_code}\n"
    path.write_text(header + (redacted if isinstance(redacted, str) else text), encoding="utf-8")


# `stream_events` is re-exported so callers (Docker runner, tests) can
# pull the stream variant when they want strict parsing.
__all__ = [
    "LocalRunner",
    "LocalRunnerError",
    "RunnerInvocation",
    "RunnerSpawnError",
    "stream_events",
]
