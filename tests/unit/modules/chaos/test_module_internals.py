"""internals of :class:`ChaosModule`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.schema import ChaosConfig, ModulesConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl

from modules.chaos import ChaosModule
from modules.chaos.module import (
    _category_skip_report,
    _read_options,
    _resolve_categories,
    _resolve_scenarios,
)
from modules.chaos.options import ChaosModuleOptions


def _config(**chaos_kwargs) -> RootConfig:
    return RootConfig(
        project={"name": "f", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl("http://127.0.0.1:8000"), "allowed_hosts": ("127.0.0.1",)},
        modules=ModulesConfig(chaos=True),
        chaos=ChaosConfig(**chaos_kwargs),
    )


def _ctx(tmp_path: Path, *, options: dict[str, Any] | None = None) -> ModuleContext:
    config = _config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-MODUNITABCDE")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    return ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="t",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-MODUNITABCDE",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def test_read_options_parses_csv_strings(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        options={
            "enabled_categories": "network, ux",
            "enabled_scenarios": "  network.api_500 , ux.duplicate_submit ",
            "flows": "checkout",
            "events_path": "/tmp/some/path.jsonl",
        },
    )
    opts = _read_options(ctx)
    assert opts.enabled_categories == ("network", "ux")
    assert opts.enabled_scenarios == ("network.api_500", "ux.duplicate_submit")
    assert opts.flows == ("checkout",)
    assert opts.events_path == Path("/tmp/some/path.jsonl")


def test_read_options_parses_list_values(tmp_path: Path) -> None:
    ctx = _ctx(
        tmp_path,
        options={
            "enabled_categories": ["network", "ux"],
            "enabled_scenarios": (),
            "flows": [],
            "events_path": Path("/tmp/p.jsonl"),
        },
    )
    opts = _read_options(ctx)
    assert opts.enabled_categories == ("network", "ux")
    assert opts.events_path == Path("/tmp/p.jsonl")


def test_read_options_ignores_unknown_types(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={"enabled_categories": 42, "events_path": None})
    opts = _read_options(ctx)
    assert opts.enabled_categories == ()
    assert opts.events_path is None


def test_resolve_categories_intersects_with_config() -> None:
    config = _config(enabled_categories=("network", "ux"))
    options = ChaosModuleOptions(enabled_categories=("ux", "data"))
    # `data` is requested but not in config → dropped.
    assert _resolve_categories(config, options) == ("ux",)


def test_resolve_scenarios_falls_back_to_catalog_when_config_blank() -> None:
    config = _config()
    options = ChaosModuleOptions()
    resolved = _resolve_scenarios(config, options, ("network",))
    assert "network.api_500" in resolved
    assert all(s.startswith("network.") for s in resolved)


def test_resolve_scenarios_respects_explicit_subset() -> None:
    config = _config()
    options = ChaosModuleOptions(enabled_scenarios=("network.api_500",))
    resolved = _resolve_scenarios(config, options, ("network",))
    assert resolved == ("network.api_500",)


def test_category_skip_report_marks_reason() -> None:
    report = _category_skip_report("network", "no events")
    assert report.skipped is True
    assert report.skip_reason == "no events"


def test_options_filter_by_flows(tmp_path: Path) -> None:
    """When flows are specified, only events matching that flow stay."""

    config = _config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-FLOWFLTABCDE")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    decision = SafetyDecision(
        allowed=True, reason="t", host="127.0.0.1", mode="safe", decided_at=datetime.now(UTC)
    )
    chaos_dir = artifacts.root / "chaos"
    chaos_dir.mkdir(parents=True, exist_ok=True)
    import json as _json

    events_path = chaos_dir / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as fh:
        fh.write(
            _json.dumps(
                {
                    "scenario_id": "network.api_500",
                    "category": "network",
                    "flow": "checkout",
                    "observation": "no_error_state",
                }
            )
            + "\n"
        )
        fh.write(
            _json.dumps(
                {
                    "scenario_id": "network.api_500",
                    "category": "network",
                    "flow": "search",
                    "observation": "no_error_state",
                }
            )
            + "\n"
        )

    ctx = ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=decision,
        artifacts=artifacts,
        run_id="RUN-FLOWFLTABCDE",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"flows": ("checkout",)},
    )
    module = ChaosModule(config=config, safety_decision=decision)
    result = module.run(ctx)
    # Both events were ingested but only "checkout" remains.
    assert len(result.findings) == 1
    assert "Flow: checkout" in result.findings[0].description


def test_metrics_emitted_when_findings_present(tmp_path: Path) -> None:
    """emit_metrics covers the non-None branch."""

    import json as _json

    config = _config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-METRICSABCDE")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    chaos_dir = artifacts.root / "chaos"
    chaos_dir.mkdir(parents=True, exist_ok=True)
    (chaos_dir / "events.jsonl").write_text(
        _json.dumps(
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "no_error_state",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ctx = ModuleContext(
        module_name="chaos",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True, reason="t", host="127.0.0.1", mode="safe", decided_at=datetime.now(UTC)
        ),
        artifacts=artifacts,
        run_id="RUN-METRICSABCDE",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={},
    )
    module = ChaosModule(config=config, safety_decision=ctx.safety_decision)
    result = module.run(ctx)
    assert result.metrics["events_bad"] == 1
    assert result.metrics["scenarios_executed"] == 1


def test_emit_metrics_returns_zeros_without_outcome(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = ChaosModule(config=ctx.config, safety_decision=ctx.safety_decision)
    # Never run; emit_metrics should give the empty payload.
    metrics = module.emit_metrics(ctx, _stub_runner_outcome(ctx))
    assert metrics == {"categories": 0}


def test_emit_findings_returns_empty_without_outcome(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = ChaosModule(config=ctx.config, safety_decision=ctx.safety_decision)
    assert module.emit_findings(ctx, _stub_runner_outcome(ctx)) == ()


def test_collect_evidence_no_op_without_outcome(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = ChaosModule(config=ctx.config, safety_decision=ctx.safety_decision)
    assert module.collect_evidence(ctx, _stub_runner_outcome(ctx)) == ()


def _stub_runner_outcome(ctx: ModuleContext):
    from engine.runner.results import EnvironmentContext, RunnerOutcome

    return RunnerOutcome.build(
        module_name="chaos",
        module_id=ctx.id_generator.new("MOD"),
        status="skipped",
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(browser="chromium", browser_version="bundled", os="unknown"),
    )
