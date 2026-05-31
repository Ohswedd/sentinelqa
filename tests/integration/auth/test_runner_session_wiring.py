"""Phase 31 — vault → LocalRunner → run-config storage_state plumbing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.auth import (
    Vault,
    cleanup_storage_state,
    materialize_storage_state,
)
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
from engine.runner.local import LocalRunner, RunnerInvocation

from tests.unit.auth.test_vault_crypto import StubKeyStore, _make_entry


class _Reader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def __aiter__(self) -> _Reader:
        return self

    async def __anext__(self) -> bytes:
        if not self._lines:
            raise StopAsyncIteration
        return self._lines.pop(0)

    async def read(self, _n: int) -> bytes:
        rest, self._lines = self._lines, []
        return b"".join(rest)


class _Process:
    def __init__(self, lines: list[bytes]) -> None:
        self.stdout = _Reader(lines)
        self.stderr = _Reader([])
        self._returncode = 0

    @property
    def returncode(self) -> int | None:
        return self._returncode

    async def wait(self) -> int:
        return self._returncode


def _event(**fields: object) -> bytes:
    payload = {
        "schema_version": "1.0.0",
        "seq": fields.pop("seq", 1),
        "ts": "2026-05-28T12:00:00+00:00",
        **fields,
    }
    return (json.dumps(payload) + "\n").encode("utf-8")


def _build_config(tmp_path: Path) -> RootConfig:
    return RootConfig(
        version=1,
        project=ProjectConfig(name="phase-31-test"),
        target=TargetConfig(
            base_url="http://example.com",
            allowed_hosts=("example.com",),
        ),
        auth=AuthConfig(strategy="browser_session", session_name="myorg"),
        modules=ModulesConfig(),
        performance=PerformanceConfig(budgets=PerformanceBudgets()),
        runner=RunnerConfig(
            workers=1,
            browser="chromium",
            headless=True,
            timeout_ms=10_000,
            retries=RunnerRetriesConfig(max=0, backoff_ms=500),
            quarantine=RunnerQuarantineConfig(path=tmp_path / "quarantine.yaml"),
        ),
    )


def test_runner_writes_storage_state_path_into_run_config(tmp_path: Path) -> None:
    """The materialized vault file flows into ``RunConfig.storage_state_path``."""

    vault_root = tmp_path / "vault"
    vault = Vault(root=vault_root, key_store=StubKeyStore())
    vault.put(_make_entry(host="example.com", name="myorg"))

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    handle = materialize_storage_state(
        vault,
        host="example.com",
        name="myorg",
        run_dir=run_dir,
        allowed_hosts={"example.com"},
    )

    config = _build_config(tmp_path)
    lines = [
        _event(
            type="run.start",
            run_id="RUN-X",
            target="http://example.com",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(
            type="run.end",
            run_id="RUN-X",
            finished_at="2026-05-28T12:00:01+00:00",
            status="passed",
            tests_total=0,
            tests_failed=0,
            seq=2,
        ),
    ]

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _Process:
        return _Process(lines)

    runner = LocalRunner(
        config=config,
        sentinel_ts_path="/usr/local/bin/sentinel-ts",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-X",
        run_dir=run_dir,
        target="http://example.com",
        module_name="functional",
        spec_files=(),
        storage_state_path=handle.path,
    )
    runner.run(invocation)
    # The run-config JSON the runner wrote MUST carry the absolute path.
    cfg_path = run_dir / "run-configs" / "functional.json"
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert payload["storage_state_path"] == str(handle.path)
    cleanup_storage_state(handle)


def test_runner_omits_storage_state_when_not_supplied(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lines = [
        _event(
            type="run.start",
            run_id="RUN-Y",
            target="http://example.com",
            started_at="2026-05-28T12:00:00+00:00",
        ),
        _event(
            type="run.end",
            run_id="RUN-Y",
            finished_at="2026-05-28T12:00:01+00:00",
            status="passed",
            tests_total=0,
            tests_failed=0,
            seq=2,
        ),
    ]

    async def fake_spawn(*_args: Any, **_kwargs: Any) -> _Process:
        return _Process(lines)

    runner = LocalRunner(
        config=config,
        sentinel_ts_path="/usr/local/bin/sentinel-ts",
        spawn_fn=fake_spawn,
    )
    invocation = RunnerInvocation(
        run_id="RUN-Y",
        run_dir=run_dir,
        target="http://example.com",
        module_name="functional",
        spec_files=(),
    )
    runner.run(invocation)
    cfg_path = run_dir / "run-configs" / "functional.json"
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert payload.get("storage_state_path") is None
