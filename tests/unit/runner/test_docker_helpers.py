"""Targeted coverage for :mod:`engine.runner.docker`."""

from __future__ import annotations

import asyncio
import shutil
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
from engine.domain.target import Target
from engine.runner.docker import (
    DockerRunner,
    DockerUnavailableError,
    _to_container_relative,
)
from engine.runner.local import RunnerInvocation, RunnerSpawnError


def _config(tmp_path: Path) -> RootConfig:
    return RootConfig(
        version=1,
        project=ProjectConfig(name="t"),
        source=SourceConfig(root=tmp_path),
        target=TargetConfig(base_url="http://localhost"),
        auth=AuthConfig(),
        modules=ModulesConfig(),
        runner=RunnerConfig(docker=True),
    )


def test_resolve_docker_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_BIN", "/custom/docker")
    target = Target(base_url="http://localhost", mode="safe")
    runner = DockerRunner(config=_config(tmp_path), target=target)
    assert runner._resolve_docker() == "/custom/docker"


def test_resolve_docker_uses_shutil_which(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCKER_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/local/bin/docker")
    target = Target(base_url="http://localhost", mode="safe")
    runner = DockerRunner(config=_config(tmp_path), target=target)
    assert runner._resolve_docker() == "/usr/local/bin/docker"


def test_resolve_docker_raises_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKER_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    target = Target(base_url="http://localhost", mode="safe")
    runner = DockerRunner(config=_config(tmp_path), target=target)
    with pytest.raises(DockerUnavailableError):
        runner._resolve_docker()


def test_to_container_relative_inside_run_dir(tmp_path: Path) -> None:
    spec = tmp_path / "tests" / "sentinel" / "a.spec.ts"
    spec.parent.mkdir(parents=True)
    spec.write_text("", encoding="utf-8")
    assert _to_container_relative(spec, tmp_path) == "tests/sentinel/a.spec.ts"


def test_to_container_relative_outside_returns_absolute(tmp_path: Path) -> None:
    out = Path("/etc/hosts")
    assert _to_container_relative(out, tmp_path).startswith("/")


def test_docker_runner_env_overrides_added_to_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = Target(base_url=config.target.base_url, mode="safe")
    monkeypatch.delenv("DOCKER_BIN", raising=False)

    seen: dict[str, Any] = {}

    async def fake_spawn(cmd: str, *args: Any, **_kw: Any) -> Any:
        seen["cmd"] = cmd
        seen["args"] = list(args)
        # Empty stdout → aggregator emits incomplete; that's fine for this test.

        class _P:
            stdout = type(
                "_R",
                (),
                {
                    "__aiter__": lambda self: self,
                    "__anext__": lambda self: (_ for _ in ()).throw(StopAsyncIteration),
                    "read": lambda self, _n: asyncio.sleep(0, result=b""),
                },
            )()
            stderr = stdout
            returncode = 0

            async def wait(self) -> int:
                return 0

        return _P()

    runner = DockerRunner(
        config=config,
        target=target,
        docker_path="/usr/local/bin/docker",
        spawn_fn=fake_spawn,
        env_overrides={"MY_KEY": "MY_VALUE"},
    )
    runner.run(
        RunnerInvocation(
            run_id="RUN-ENVAAAAAAAAA",
            run_dir=tmp_path,
            target="http://localhost",
            module_name="functional",
            spec_files=[],
        )
    )

    args = seen["args"]
    # Look for the MY_KEY=MY_VALUE env injection.
    assert any(a == "MY_KEY=MY_VALUE" for a in args)


def test_docker_runner_os_error_surfaces_as_spawn_error(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    target = Target(base_url=config.target.base_url, mode="safe")

    async def fake_spawn(*_a: Any, **_kw: Any) -> Any:
        raise OSError("no docker today")

    runner = DockerRunner(
        config=config,
        target=target,
        docker_path="/usr/local/bin/docker",
        spawn_fn=fake_spawn,
    )
    with pytest.raises(RunnerSpawnError):
        runner.run(
            RunnerInvocation(
                run_id="RUN-OSAAAAAAAAAB",
                run_dir=tmp_path,
                target="http://localhost",
                module_name="functional",
                spec_files=[],
            )
        )
