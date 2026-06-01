"""Unit tests for :mod:`modules.functional`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext, ModulePrerequisiteError, SentinelModule
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry
from engine.policy.safety import SafetyDecision
from engine.runner.local import RunnerInvocation
from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
)

from modules.functional import (
    FunctionalModule,
    FunctionalModuleOptions,
    register_with_default_registry,
)
from modules.functional.module import _factory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_config(root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n",
        encoding="utf-8",
    )
    return p


def _build_ctx(
    tmp_path: Path,
    *,
    base_url: str = "http://localhost:3000",
    options: Mapping[str, Any] | None = None,
) -> ModuleContext:
    config_path = _write_config(tmp_path, base_url=base_url)
    config = load_config(config_path)
    artifacts_root = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(artifacts_root)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="functional",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=artifacts_root,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def _build_outcome(*, status: str = "passed", failures: int = 0) -> RunnerOutcome:
    tests: list[TestExecution] = []
    for i in range(failures):
        tests.append(
            TestExecution(
                test_id=f"t-{i}",
                title=f"failing test {i}",
                file=f"tests/sentinel/spec_{i}.spec.ts",
                status="failed",
                duration_ms=200,
                retries=0,
                evidence=("traces/spec_0.zip",),
                error_message="boom",
            )
        )
    if failures == 0 and status == "passed":
        tests.append(
            TestExecution(
                test_id="t-pass",
                title="happy path",
                file="tests/sentinel/happy.spec.ts",
                status="passed",
                duration_ms=120,
                retries=0,
            )
        )
    return RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-AAAAAAAAAAAA",
        status="failed" if failures > 0 else "passed",
        tests=tuple(tests),
        duration_ms=200,
        environment=EnvironmentContext(
            browser="chromium",
            browser_version="bundled",
            os="linux-test",
        ),
    )


class _StubRunner:
    """Records the invocation; returns a canned :class:`RunnerOutcome`."""

    def __init__(self, outcome: RunnerOutcome) -> None:
        self._outcome = outcome
        self.received: RunnerInvocation | None = None

    def run(self, invocation: RunnerInvocation) -> RunnerOutcome:
        self.received = invocation
        return self._outcome


# ---------------------------------------------------------------------------
# Module class basics
# ---------------------------------------------------------------------------


def test_functional_module_is_sentinel_module(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(ctx.config, ctx.safety_decision)
    assert isinstance(module, SentinelModule)
    assert FunctionalModule.name == "functional"


def test_factory_returns_functional_module_instance(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    instance = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(instance, FunctionalModule)


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def test_validate_prerequisites_is_noop_with_injected_runner(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    runner = _StubRunner(_build_outcome())
    module = FunctionalModule(
        ctx.config,
        ctx.safety_decision,
        runner_factory=lambda _cfg, _sd: runner,
    )
    module.validate_prerequisites(ctx)  # no exception


def test_validate_prerequisites_is_noop_with_default_factory(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(ctx.config, ctx.safety_decision)
    # validate_prerequisites is intentionally a no-op (the sentinel-ts
    # probe was moved inside execute — see modules/functional/module.py).
    module.validate_prerequisites(ctx)


def test_execute_with_default_factory_raises_when_sentinel_ts_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sentinel-ts is required only when there are specs to run."""

    spec_root = tmp_path / "specs"
    spec_root.mkdir()
    (spec_root / "a.spec.ts").write_text("// a", encoding="utf-8")
    monkeypatch.delenv("SENTINEL_TS_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    ctx = _build_ctx(tmp_path, options={"spec_root": spec_root})
    module = FunctionalModule(ctx.config, ctx.safety_decision)
    specs = module.plan(ctx)
    with pytest.raises(ModulePrerequisiteError):
        module.execute(ctx, specs)


# ---------------------------------------------------------------------------
# Planning + execution
# ---------------------------------------------------------------------------


def test_plan_returns_empty_when_spec_root_missing(tmp_path: Path) -> None:
    ctx = _build_ctx(
        tmp_path,
        options={"spec_root": tmp_path / "nonexistent"},
    )
    runner = _StubRunner(_build_outcome())
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    assert module.plan(ctx) == ()


def test_plan_lists_spec_files_alphabetically(tmp_path: Path) -> None:
    spec_root = tmp_path / "specs"
    spec_root.mkdir()
    (spec_root / "b.spec.ts").write_text("// b", encoding="utf-8")
    (spec_root / "a.spec.ts").write_text("// a", encoding="utf-8")
    (spec_root / "nested").mkdir()
    (spec_root / "nested" / "c.spec.ts").write_text("// c", encoding="utf-8")
    ctx = _build_ctx(tmp_path, options={"spec_root": spec_root})
    module = FunctionalModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: _StubRunner(_build_outcome())
    )
    specs = module.plan(ctx)
    assert [s.name for s in specs] == ["a.spec.ts", "b.spec.ts", "c.spec.ts"]


def test_execute_with_no_specs_returns_empty_outcome(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path, options={"spec_root": tmp_path / "nope"})
    runner = _StubRunner(_build_outcome())
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    outcome = module.execute(ctx, ())
    assert outcome.module_result.status == "skipped"
    assert outcome.module_result.metrics["tests_total"] == 0
    assert runner.received is None


def test_execute_forwards_invocation_to_runner(tmp_path: Path) -> None:
    spec_root = tmp_path / "specs"
    spec_root.mkdir()
    spec = spec_root / "demo.spec.ts"
    spec.write_text("// demo", encoding="utf-8")

    ctx = _build_ctx(
        tmp_path,
        options={"spec_root": spec_root, "grep": "@p0", "workers": 4},
    )
    runner = _StubRunner(_build_outcome())
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    specs = module.plan(ctx)
    module.execute(ctx, specs)
    assert runner.received is not None
    assert runner.received.grep == "@p0"
    assert runner.received.workers == 4
    assert runner.received.module_name == "functional"
    assert runner.received.spec_files == specs


# ---------------------------------------------------------------------------
# Findings translation
# ---------------------------------------------------------------------------


def test_emit_findings_translates_failures_with_evidence(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    runner = _StubRunner(_build_outcome())
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    outcome = _build_outcome(failures=2)
    findings = module.emit_findings(ctx, outcome)
    assert len(findings) == 2
    for f in findings:
        assert f.module == "functional"
        assert f.severity == "high"
        assert f.affected_target == "http://localhost:3000/"
        assert f.confidence == 0.9
        assert len(f.reproduction_steps) == 2
        assert any(e.type == "trace" for e in f.evidence)


def test_emit_findings_respects_quarantine(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: _StubRunner(_build_outcome())
    )
    outcome = _build_outcome(failures=1)
    # Force quarantine of the failing test id.
    outcome = outcome.model_copy(update={"quarantined_test_ids": ("t-0",)})
    findings = module.emit_findings(ctx, outcome)
    assert findings == ()


def test_emit_metrics_pass_through_runner(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = FunctionalModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: _StubRunner(_build_outcome())
    )
    outcome = _build_outcome()
    metrics = module.emit_metrics(ctx, outcome)
    assert metrics["tests_passed"] >= 1


def test_summarize_overlays_findings_on_runner_module_result(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    runner = _StubRunner(_build_outcome(failures=1))
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    outcome = _build_outcome(failures=1)
    findings = module.emit_findings(ctx, outcome)
    metrics = module.emit_metrics(ctx, outcome)
    summary = module.summarize(ctx, outcome, findings, metrics)
    assert summary.status == "failed"
    assert len(summary.findings) == 1
    assert summary.findings[0].module == "functional"


# ---------------------------------------------------------------------------
# Full run + options round-trip
# ---------------------------------------------------------------------------


def test_run_orchestrates_full_lifecycle(tmp_path: Path) -> None:
    spec_root = tmp_path / "specs"
    spec_root.mkdir()
    (spec_root / "demo.spec.ts").write_text("// d", encoding="utf-8")
    runner = _StubRunner(_build_outcome(failures=2))
    ctx = _build_ctx(
        tmp_path,
        options={"spec_root": spec_root, "grep": "@flow:login"},
    )
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    result = module.run(ctx)
    assert result.status == "failed"
    assert len(result.findings) == 2
    assert runner.received is not None
    assert runner.received.grep == "@flow:login"


def test_functional_module_options_dataclass_default_immutable() -> None:
    from dataclasses import FrozenInstanceError

    opts = FunctionalModuleOptions()
    assert opts.spec_root is None
    assert opts.grep is None
    assert dict(opts.extra_env) == {}
    with pytest.raises(FrozenInstanceError):
        opts.grep = "@p0"  # type: ignore[misc]


def test_run_accepts_functional_options_typed_dataclass(tmp_path: Path) -> None:
    spec_root = tmp_path / "specs"
    spec_root.mkdir()
    (spec_root / "a.spec.ts").write_text("// a", encoding="utf-8")
    runner = _StubRunner(_build_outcome())
    typed_options = FunctionalModuleOptions(spec_root=spec_root, grep="@p1")
    ctx = _build_ctx(tmp_path, options={"functional": typed_options})
    module = FunctionalModule(ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner)
    module.run(ctx)
    assert runner.received is not None
    assert runner.received.grep == "@p1"


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def test_register_with_default_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "functional" in registry.modules


def test_register_with_explicit_registry_records_factory() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    factory = registry.modules["functional"]
    assert factory is _factory
