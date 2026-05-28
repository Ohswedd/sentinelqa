"""Lifecycle integration: SentinelModule factories run the seven-step lifecycle.

Phase 10 introduced the convention that a module factory may return a
:class:`engine.modules.base.SentinelModule` instance. When it does, the
orchestrator calls :meth:`SentinelModule.run` and merges typed findings
into the lifecycle's context. This test pins that behavior so future
phases can extend it without regression.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.config.loader import load_config
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.registry import ModuleRegistry
from engine.orchestrator.run_lifecycle import RunLifecycle
from engine.runner.results import EnvironmentContext, RunnerOutcome, TestExecution


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: true\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def _make_outcome(*, failing: int = 0) -> RunnerOutcome:
    tests: list[TestExecution] = []
    if failing:
        tests.append(
            TestExecution(
                test_id="t1",
                title="t1",
                file="t.spec.ts",
                status="failed",
                duration_ms=100,
                retries=0,
            )
        )
    else:
        tests.append(
            TestExecution(
                test_id="t1",
                title="t1",
                file="t.spec.ts",
                status="passed",
                duration_ms=100,
                retries=0,
            )
        )
    return RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-AAAAAAAAAAAA",
        status="failed" if failing else "passed",
        tests=tuple(tests),
        duration_ms=100,
        environment=EnvironmentContext(
            browser="chromium", browser_version="bundled", os="linux-test"
        ),
    )


class _StaticModule(SentinelModule):
    name = "functional"

    def __init__(
        self,
        cfg: Any,
        sd: Any,
        *,
        outcome: RunnerOutcome,
    ) -> None:
        super().__init__(cfg, sd)
        self._outcome = outcome

    def execute(self, ctx: ModuleContext, specs: Any) -> RunnerOutcome:
        return self._outcome


def test_lifecycle_invokes_sentinel_module_and_collects_typed_results(
    tmp_path: Path,
) -> None:
    config = load_config(_write_config(tmp_path))
    outcome = _make_outcome(failing=1)

    registry = ModuleRegistry()
    registry.register_module(
        "functional",
        lambda c, s: _StaticModule(c, s, outcome=outcome),
    )
    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])

    ctx = lifecycle.last_context
    assert ctx is not None
    assert len(ctx.typed_module_results) == 1
    mod_result = ctx.typed_module_results[0]
    assert mod_result.name == "functional"
    assert mod_result.status == "failed"
    assert len(ctx.typed_findings) == 1
    # ModuleOutcome metadata records the wired-in finding count.
    [outcome_record] = ctx.module_outcomes
    assert outcome_record.metadata["findings"] == 1
    assert outcome_record.metadata["module_status"] == "failed"
    # And the run rolls up to "passed" because the lifecycle hasn't yet
    # wired finding-driven gates; Phase 14 owns that.
    assert test_run.status in {"passed", "incomplete"}


def test_lifecycle_propagates_module_options_into_module_context(
    tmp_path: Path,
) -> None:
    config = load_config(_write_config(tmp_path))
    seen: dict[str, Any] = {}

    class _SpyModule(SentinelModule):
        name = "functional"

        def execute(self, ctx: ModuleContext, specs: Any) -> RunnerOutcome:
            seen["options"] = dict(ctx.options)
            seen["run_id"] = ctx.run_id
            return _make_outcome(failing=0)

    registry = ModuleRegistry()
    registry.register_module(
        "functional",
        lambda c, s: _SpyModule(c, s),
    )
    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    lifecycle.execute(
        config,
        requested_modules=["functional"],
        module_options={"functional": {"grep": "@p0", "spec_root": None}},
    )
    assert seen["options"] == {"grep": "@p0", "spec_root": None}
    assert seen["run_id"].startswith("RUN-")


def test_lifecycle_module_prerequisite_error_records_errored_outcome(
    tmp_path: Path,
) -> None:
    from engine.modules.base import ModulePrerequisiteError

    config = load_config(_write_config(tmp_path))

    class _BadModule(SentinelModule):
        name = "functional"

        def validate_prerequisites(self, ctx: ModuleContext) -> None:
            raise ModulePrerequisiteError("missing dependency XYZ")

        def execute(self, ctx: ModuleContext, specs: Any) -> RunnerOutcome:
            raise AssertionError("execute should never run after a prereq failure")

    registry = ModuleRegistry()
    registry.register_module(
        "functional",
        lambda c, s: _BadModule(c, s),
    )
    lifecycle = RunLifecycle(
        artifacts_root=tmp_path / ".sentinel" / "runs",
        registry=registry,
    )
    test_run = lifecycle.execute(config, requested_modules=["functional"])
    assert test_run.status == "incomplete"
    [outcome_record] = lifecycle.last_context.module_outcomes  # type: ignore[union-attr]
    assert outcome_record.status == "errored"
    assert outcome_record.error_type == "ModulePrerequisiteError"
