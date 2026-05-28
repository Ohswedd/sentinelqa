"""Integration tests for :class:`DockerRunner` (08.02).

The Docker subprocess is faked the same way as for the local runner —
we never launch a real container. What we do verify:

  - The docker command line is correctly assembled (read-only source
    mount, writable run-dir mount, ``host.docker.internal`` alias).
  - Safety policy is enforced again before container spawn.
  - The container-side run-config rewrites paths to ``/sentinel/run``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import (
    AuthConfig,
    ModulesConfig,
    PerformanceConfig,
    ProjectConfig,
    RootConfig,
    RunnerConfig,
    RunnerQuarantineConfig,
    SecurityConfig,
    SourceConfig,
    TargetConfig,
)
from engine.domain.target import Target
from engine.errors.base import UnsafeTargetError
from engine.runner.docker import (
    DockerRunner,
    DockerUnavailableError,
)
from engine.runner.local import RunnerInvocation


def _event_jsonl() -> list[bytes]:
    payload = {
        "schema_version": "1.0.0",
        "type": "run.start",
        "run_id": "RUN-FAKE",
        "target": "http://localhost",
        "started_at": "2026-05-28T12:00:00+00:00",
        "seq": 1,
        "ts": "2026-05-28T12:00:00+00:00",
    }
    end = {
        "schema_version": "1.0.0",
        "type": "run.end",
        "run_id": "RUN-FAKE",
        "finished_at": "2026-05-28T12:00:01+00:00",
        "status": "passed",
        "tests_total": 0,
        "tests_failed": 0,
        "seq": 2,
        "ts": "2026-05-28T12:00:00+00:00",
    }
    return [
        (json.dumps(payload) + "\n").encode("utf-8"),
        (json.dumps(end) + "\n").encode("utf-8"),
    ]


class _FakeReader:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self) -> _FakeReader:
        return self

    async def __anext__(self) -> bytes:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def read(self, _n: int) -> bytes:
        if not self._chunks:
            return b""
        chunk = b"".join(self._chunks)
        self._chunks.clear()
        return chunk


class _FakeProcess:
    def __init__(self, stdout_chunks: list[bytes]) -> None:
        self.stdout = _FakeReader(stdout_chunks)
        self.stderr = _FakeReader([])
        self._rc = 0

    @property
    def returncode(self) -> int | None:
        return self._rc

    async def wait(self) -> int:
        return self._rc


def _build_config(tmp_path: Path) -> RootConfig:
    return RootConfig(
        version=1,
        project=ProjectConfig(name="docker-test"),
        source=SourceConfig(root=tmp_path),
        target=TargetConfig(base_url="http://localhost"),
        auth=AuthConfig(),
        modules=ModulesConfig(),
        performance=PerformanceConfig(),
        security=SecurityConfig(),
        runner=RunnerConfig(
            workers=1,
            browser="chromium",
            docker=True,
            docker_image="mcr.microsoft.com/playwright:v1.49.0-jammy",
            quarantine=RunnerQuarantineConfig(path=tmp_path / "q.yaml"),
        ),
    )


def test_docker_command_includes_required_mounts_and_image(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    target = Target(base_url=config.target.base_url, mode="safe")
    seen: dict[str, Any] = {}

    async def fake_spawn(cmd: str, *args: Any, **_kw: Any) -> _FakeProcess:
        seen["cmd"] = cmd
        seen["args"] = list(args)
        return _FakeProcess(_event_jsonl())

    runner = DockerRunner(
        config=config,
        target=target,
        docker_path="/usr/local/bin/docker",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-DOCKAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[],
    )
    outcome = runner.run(invocation)

    assert outcome.module_result.status == "passed"
    cmd = seen["cmd"]
    args = seen["args"]
    assert cmd == "/usr/local/bin/docker"
    assert args[0] == "run"
    # The pinned image is at the end (just before `sentinel-ts ...`).
    assert "mcr.microsoft.com/playwright:v1.49.0-jammy" in args
    # host.docker.internal alias is present.
    assert any(
        a == "--add-host" and args[i + 1].startswith("host.docker.internal")
        for i, a in enumerate(args[:-1])
    )
    # The source mount is read-only; the run-dir mount is writable.
    mounts = [a for a in args if a.startswith("type=bind")]
    assert any("readonly" in m for m in mounts)
    assert any("readonly" not in m and "/sentinel/run" in m for m in mounts)
    # No --privileged or socket mounts.
    assert "--privileged" not in args
    assert all("/var/run/docker.sock" not in a for a in args)


def test_docker_runner_blocks_unsafe_target(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    # Public target with no allowlist → SafetyPolicy will block.
    public_target = Target(
        base_url="http://example.com",
        allowed_hosts=frozenset(),
        mode="safe",
    )

    async def fake_spawn(*_a: Any, **_kw: Any) -> _FakeProcess:  # pragma: no cover
        raise AssertionError("spawn must not happen for unsafe targets")

    runner = DockerRunner(
        config=config,
        target=public_target,
        docker_path="/usr/local/bin/docker",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-UNSAFAAAAAAA",
        run_dir=tmp_path,
        target=str(public_target.base_url),
        module_name="functional",
        spec_files=[],
    )
    with pytest.raises(UnsafeTargetError):
        runner.run(invocation)


def test_docker_runner_surface_missing_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config(tmp_path)
    target = Target(base_url=config.target.base_url, mode="safe")
    monkeypatch.delenv("DOCKER_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)

    runner = DockerRunner(config=config, target=target)
    invocation = RunnerInvocation(
        run_id="RUN-NOPEAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[],
    )
    with pytest.raises(DockerUnavailableError):
        runner.run(invocation)


def test_docker_runner_writes_container_relative_run_config(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    target = Target(base_url=config.target.base_url, mode="safe")

    async def fake_spawn(*_a: Any, **_kw: Any) -> _FakeProcess:
        return _FakeProcess(_event_jsonl())

    runner = DockerRunner(
        config=config,
        target=target,
        docker_path="/usr/local/bin/docker",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-CTRRAAAAAAAA",
        run_dir=tmp_path,
        target="http://localhost",
        module_name="functional",
        spec_files=[],
    )
    runner.run(invocation)

    cfg = json.loads(
        (tmp_path / "run-configs" / "functional.docker.json").read_text(encoding="utf-8")
    )
    assert cfg["run_dir"] == "/sentinel/run"
    assert cfg["headless"] is True
