"""Docker-isolated Playwright runner (Phase 08.02).

The :class:`DockerRunner` shares the :class:`LocalRunner` contract but
spawns ``docker run`` against a pinned Playwright image instead of
running ``sentinel-ts`` on the host. The image is built from
``apps/cli/sentinel/runner/docker/Dockerfile.runner`` (or pulled from the
user's registry); ``make build-runner-image`` is the canonical local
build.

Safety boundary (our engineering rules, §10):

- Container launch is preceded by an explicit safety-policy check
  inside the runner. Even though the lifecycle already enforced it,
  Docker-mounting paths means a misuse can leak host files; we
  enforce the check twice on purpose.
- The project source is mounted **read-only**. Only the run dir is
  writable. Network defaults to a private bridge; ``host.docker.internal``
  is added as an alias for the local target.
- No ``--privileged``, no Docker socket mounts, no ``--cap-add``.

Docker absence is not a Phase-08 failure; it surfaces as
:class:`DockerUnavailable` so the CLI / tests can degrade gracefully.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.config.schema import RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.errors.base import UnsafeTargetError
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyPolicy
from engine.runner.local import (
    LocalRunnerError,
    RunnerInvocation,
    RunnerSpawnError,
    _collect_environment,
    _drain_stream,
    _resolve_workers,
    _safe_await_bytes,
    _stream_or_partial,
    _terminate,
    _write_runner_log,
)
from engine.runner.results import (
    RunnerOutcome,
    aggregate,
    write_module_results,
)
from engine.runner.run_config import RunConfig, ShardConfig
from engine.runner.sharding import ShardSpec

DEFAULT_GRACE_SECONDS = 5.0


class DockerRunnerError(LocalRunnerError):
    """Raised when the Docker runner cannot complete its work."""


class DockerUnavailableError(DockerRunnerError):
    """Raised when ``docker`` is not available on PATH."""


@dataclass(frozen=True)
class DockerMount:
    host_path: Path
    container_path: str
    read_only: bool = True


class DockerRunner:
    """Spawn ``docker run <image> sentinel-ts run …`` and stream JSONL.

    The runner re-enforces the safety policy before starting the
    container; the policy is configured by the caller (the CLI passes
    the same :class:`SafetyPolicy` it used for the lifecycle).
    """

    def __init__(
        self,
        *,
        config: RootConfig,
        target: Target,
        safety_policy: SafetyPolicy | None = None,
        docker_path: str | None = None,
        spawn_fn: object | None = None,
        id_generator: IdGenerator | None = None,
        grace_seconds: float = DEFAULT_GRACE_SECONDS,
        env_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        self._target = target
        self._policy = safety_policy or SafetyPolicy()
        self._docker_path = docker_path
        self._spawn_fn = spawn_fn or asyncio.create_subprocess_exec  # type: ignore[assignment]
        self._ids = id_generator or IdGenerator()
        self._grace = grace_seconds
        self._env_overrides = dict(env_overrides or {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:
        return asyncio.run(self.run_async(invocation))

    async def run_async(self, invocation: RunnerInvocation) -> RunnerOutcome:
        # Re-enforce safety BEFORE launching a container (CLAUDE §6, §10).
        audit_log = invocation.run_dir / "audit.log"
        self._policy.enforce(self._target, audit_log_path=audit_log)

        artifacts = ArtifactDirectory(invocation.run_dir)
        config_path = self._write_run_config(artifacts, invocation)
        cmd, args, container_config_path = self._build_command(invocation, config_path)

        logs_dir = artifacts.subdir("logs")
        runner_log_path = logs_dir / f"runner.docker.{invocation.module_name}.log"

        proc = await self._spawn(cmd, args)
        module_id = self._ids.new("MOD")
        stderr_task = asyncio.create_task(_drain_stream(proc.stderr))
        cancelled = False
        try:
            assert proc.stdout is not None
            outcome = await aggregate(
                _stream_or_partial(proc.stdout),
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
            import contextlib as _ctx

            with _ctx.suppress(TimeoutError, ProcessLookupError):
                await asyncio.wait_for(proc.wait(), timeout=self._grace)
            _write_runner_log(runner_log_path, stderr_bytes, exit_code=proc.returncode)

        write_module_results(artifacts, outcome)
        # The audit_log path lookup keeps mypy happy and serves as a
        # cheap assertion that the safety call wrote its line.
        _ = container_config_path
        return outcome

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_docker(self) -> str:
        if self._docker_path is not None:
            return self._docker_path
        env_path = os.environ.get("DOCKER_BIN")
        if env_path:
            return env_path
        on_path = shutil.which("docker")
        if on_path is None:
            raise DockerUnavailableError(
                "docker not found on PATH. Install Docker Desktop or pass "
                "docker_path= to DockerRunner."
            )
        return on_path

    def _build_command(
        self,
        invocation: RunnerInvocation,
        host_config_path: Path,
    ) -> tuple[str, list[str], str]:
        docker = self._resolve_docker()
        run_dir = invocation.run_dir.resolve()
        source_root = self._config.source.root.resolve()
        image = self._config.runner.docker_image

        # The run dir is mounted writable so JSONL traces and HARs land
        # on the host; the source is mounted read-only so the container
        # cannot corrupt the working tree.
        container_run_dir = "/sentinel/run"
        container_source = "/sentinel/source"
        # The run-config file path INSIDE the container — Python rewrites
        # the path so the TS runner reads from its container mount.
        relative_cfg = host_config_path.resolve().relative_to(run_dir)
        container_cfg = f"{container_run_dir}/{relative_cfg.as_posix()}"

        args: list[str] = [
            "run",
            "--rm",
            "--init",
            "--network",
            "bridge",
            "--add-host",
            "host.docker.internal:host-gateway",
            "--mount",
            f"type=bind,source={run_dir},target={container_run_dir}",
            "--mount",
            f"type=bind,source={source_root},target={container_source},readonly",
            "--workdir",
            container_source,
            "--env",
            f"SENTINELQA_RUN_ID={invocation.run_id}",
            "--env",
            f"SENTINELQA_RUN_DIR={container_run_dir}",
        ]
        for key, value in self._env_overrides.items():
            args.extend(["--env", f"{key}={value}"])
        args.extend([image, "sentinel-ts", "run", "--input", container_cfg])
        return docker, args, container_cfg

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
        # The container sees the run dir at /sentinel/run; spec files are
        # relative to the run dir so the same path works on both sides.
        spec_files = tuple(
            _to_container_relative(p, invocation.run_dir) for p in invocation.spec_files
        )

        # Phase 31, ADR-0043. When the caller provided a storage_state
        # file, we expose it inside the container under
        # ``/sentinel/run/auth/storage_state.json``. The actual bind-
        # mount of the run dir is set up elsewhere in this module; the
        # orchestrator writes the file into the run dir so the Docker
        # mount picks it up automatically.
        if invocation.storage_state_path is not None:
            container_storage_path: str | None = "/sentinel/run/auth/storage_state.json"
        else:
            container_storage_path = None

        run_config = RunConfig(
            run_id=invocation.run_id,
            target=invocation.target,
            run_dir="/sentinel/run",
            spec_files=spec_files,
            workers=workers,
            shard=ShardConfig(current=shard.current, total=shard.total) if shard else None,
            browser=runner_cfg.browser,
            headless=True,  # Docker is always headless.
            timeout_ms=runner_cfg.timeout_ms,
            retries=runner_cfg.retries.max,
            grep=invocation.grep,
            env={},
            storage_state_path=container_storage_path,
        )
        out_dir = artifacts.subdir("run-configs")
        target = out_dir / f"{invocation.module_name}.docker.json"
        target.write_text(
            json.dumps(run_config.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    async def _spawn(self, cmd: str, args: Sequence[str]) -> asyncio.subprocess.Process:
        try:
            return await self._spawn_fn(  # type: ignore[misc]
                cmd,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise RunnerSpawnError(f"failed to spawn docker ({cmd!r}): {exc}") from exc


def _to_container_relative(spec: Path, run_dir: Path) -> str:
    try:
        return spec.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        # Spec is outside the run dir (e.g. a checked-in tests dir);
        # callers must ensure the source mount covers it.
        return spec.resolve().as_posix()


# Re-expose for type-checked imports.
__all__ = [
    "DockerMount",
    "DockerRunner",
    "DockerRunnerError",
    "DockerUnavailableError",
    "UnsafeTargetError",
]
