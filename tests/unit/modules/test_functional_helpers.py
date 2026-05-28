"""Coverage for the private helpers in :mod:`modules.functional.module`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.config.schema import RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from engine.runner import DockerRunner, LocalRunner, Quarantine

from modules.functional.module import (
    FunctionalModuleOptions,
    _coerce_path,
    _default_runner_factory,
    _empty_outcome,
    _load_quarantine,
    _read_options,
)


def _config(tmp_path: Path, *, docker: bool = False) -> RootConfig:
    p = tmp_path / "sentinel.config.yaml"
    body = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
    )
    if docker:
        body += "runner:\n  docker: true\n"
    p.write_text(body, encoding="utf-8")
    return load_config(p)


def _ctx(tmp_path: Path, *, options: Any = None) -> ModuleContext:
    cfg = _config(tmp_path)
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=cfg.target.base_url,
        allowed_hosts=frozenset(cfg.target.allowed_hosts),
        mode=cfg.security.mode,
        proof_of_authorization=cfg.target.proof_of_authorization,
    )
    return ModuleContext(
        module_name="functional",
        config=cfg,
        safety_decision=SafetyDecision(
            host="localhost",
            mode="safe",
            allowed=True,
            reason="t",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


# ---------------------------------------------------------------------------
# _read_options
# ---------------------------------------------------------------------------


def test_read_options_returns_defaults_when_options_is_empty(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={})
    opts = _read_options(ctx)
    assert opts == FunctionalModuleOptions()


def test_read_options_dict_under_functional_key(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={"functional": {"grep": "@p0", "workers": 3}})
    opts = _read_options(ctx)
    assert opts.grep == "@p0"
    assert opts.workers == 3


def test_read_options_typed_dataclass_under_functional_key(tmp_path: Path) -> None:
    sentinel = FunctionalModuleOptions(grep="@p1")
    ctx = _ctx(tmp_path, options={"functional": sentinel})
    opts = _read_options(ctx)
    assert opts is sentinel


def test_read_options_flat_dict_returns_defaults_for_unsupported_shape(
    tmp_path: Path,
) -> None:
    # The CLI threads {"functional": {...}}; a raw value that isn't a
    # dict / FunctionalModuleOptions / mapping with the functional key
    # falls back to defaults so the module never crashes on a typo.
    ctx = _ctx(tmp_path, options={"unrelated": "value"})
    opts = _read_options(ctx)
    assert opts == FunctionalModuleOptions()


def test_read_options_functional_key_with_unsupported_value_falls_back(
    tmp_path: Path,
) -> None:
    # If a caller hands us ``{"functional": <non-dict non-options>}``,
    # we accept the misuse and return defaults rather than crash.
    ctx = _ctx(tmp_path, options={"functional": "garbage"})
    opts = _read_options(ctx)
    assert opts == FunctionalModuleOptions()


# ---------------------------------------------------------------------------
# _coerce_path
# ---------------------------------------------------------------------------


def test_coerce_path_none_returns_none() -> None:
    assert _coerce_path(None) is None


def test_coerce_path_with_path_returns_same(tmp_path: Path) -> None:
    p = tmp_path / "x"
    assert _coerce_path(p) is p


def test_coerce_path_with_string_wraps_in_path() -> None:
    assert _coerce_path("relative/dir") == Path("relative/dir")


# ---------------------------------------------------------------------------
# _load_quarantine
# ---------------------------------------------------------------------------


def test_load_quarantine_missing_file_returns_empty(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    q = _load_quarantine(cfg)
    assert isinstance(q, Quarantine)
    assert q.test_ids() == ()


def test_load_quarantine_malformed_file_falls_back_to_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = _config(tmp_path)
    qpath = Path(cfg.runner.quarantine.path)
    qpath.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately bad YAML structure that the loader rejects.
    qpath.write_text("- not-a-quarantine-entry\n", encoding="utf-8")
    q = _load_quarantine(cfg)
    assert q.test_ids() == ()


# ---------------------------------------------------------------------------
# _default_runner_factory
# ---------------------------------------------------------------------------


def test_default_runner_factory_returns_local_runner(tmp_path: Path) -> None:
    cfg = _config(tmp_path, docker=False)
    sd = SafetyDecision(
        host="localhost", mode="safe", allowed=True, reason="t", decided_at=datetime.now(UTC)
    )
    runner = _default_runner_factory(cfg, sd)
    assert isinstance(runner, LocalRunner)


def test_default_runner_factory_returns_docker_runner(tmp_path: Path) -> None:
    cfg = _config(tmp_path, docker=True)
    sd = SafetyDecision(
        host="localhost", mode="safe", allowed=True, reason="t", decided_at=datetime.now(UTC)
    )
    runner = _default_runner_factory(cfg, sd)
    assert isinstance(runner, DockerRunner)


# ---------------------------------------------------------------------------
# _empty_outcome
# ---------------------------------------------------------------------------


def test_empty_outcome_status_is_skipped(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    outcome = _empty_outcome(ctx)
    assert outcome.module_result.status == "skipped"
    assert outcome.module_result.metrics["tests_total"] == 0
