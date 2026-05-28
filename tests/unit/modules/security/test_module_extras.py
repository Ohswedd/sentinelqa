"""Extra coverage tests for :class:`SecurityModule` (Phase 13.13)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from engine.runner.results import EnvironmentContext, RunnerOutcome

from modules.security import SecurityModule
from modules.security.models import (
    SECURITY_RESULT_SCHEMA_VERSION,
    SecurityCheckResult,
    SecurityIssue,
    SecurityRunOutcome,
)
from modules.security.module import (
    _read_options,
    _route_slug,
    _routes_from_discovery,
)
from modules.security.options import SecurityModuleOptions


def _ctx(tmp_path: Path, *, options: dict[str, Any] | None = None) -> ModuleContext:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:8088\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="security",
        config=config,
        safety_decision=safety,
        artifacts=ArtifactDirectory(run_dir),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def _outcome(*, skipped: bool = False) -> SecurityRunOutcome:
    issue = SecurityIssue(
        rule_id="SEC-HEADERS-HSTS-MISSING",
        severity="high",
        confidence=0.9,
        title="HSTS missing",
        description="missing on https",
        route="/",
    )
    issues: tuple[SecurityIssue, ...] = () if skipped else (issue,)
    return SecurityRunOutcome(
        schema_version=SECURITY_RESULT_SCHEMA_VERSION,
        checks=(
            SecurityCheckResult(
                check="headers",
                targets_scanned=1,
                issues=issues,
                duration_ms=10,
                skipped=skipped,
                skipped_reason="x" if skipped else None,
            ),
        ),
        duration_ms=10,
        incomplete=False,
    )


def test_read_options_accepts_dict_with_string_route(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={"security": {"routes": "/single"}})
    options = _read_options(ctx)
    assert options.routes == ("/single",)


def test_read_options_accepts_options_instance(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={"security": SecurityModuleOptions(routes=("/a",))})
    options = _read_options(ctx)
    assert options.routes == ("/a",)


def test_read_options_accepts_dict_without_wrapper(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={"routes": ("/a",), "discovery_path": "/tmp/d.json"})
    options = _read_options(ctx)
    assert options.routes == ("/a",)
    assert options.discovery_path == Path("/tmp/d.json")


def test_read_options_default(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, options={})
    options = _read_options(ctx)
    assert options.routes == ()


def test_routes_from_discovery_handles_missing(tmp_path: Path) -> None:
    assert _routes_from_discovery(tmp_path / "nope.json") == ()


def test_routes_from_discovery_extracts_paths(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    path.write_text(
        '{"routes": [{"path": "/a"}, "/b", {"route": "/c"}, "/a"]}',
        encoding="utf-8",
    )
    routes = _routes_from_discovery(path)
    assert routes == ("/a", "/b", "/c")


def test_routes_from_discovery_handles_garbage(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    path.write_text("not json", encoding="utf-8")
    assert _routes_from_discovery(path) == ()


def test_route_slug_handles_root_and_special_chars() -> None:
    assert _route_slug("/") == "root"
    assert _route_slug("") == "root"
    assert _route_slug("/api/users") == "api-users"
    assert _route_slug("/!!!") == "root"


def test_module_emit_findings_when_outcome_none(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    findings = module.emit_findings(ctx, _stub_runner_outcome())
    assert findings == ()


def test_module_emit_metrics_when_outcome_none(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    metrics = module.emit_metrics(ctx, _stub_runner_outcome())
    assert metrics["checks"] == 0


def test_module_collect_evidence_writes_index_and_per_check(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module._last_outcome = _outcome()
    module.collect_evidence(ctx, _stub_runner_outcome())
    sec_dir = ctx.run_dir / "security"
    assert (sec_dir / "index.json").exists()
    assert (sec_dir / "headers.json").exists()


def test_module_emit_findings_with_outcome(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module._last_outcome = _outcome()
    findings = module.emit_findings(ctx, _stub_runner_outcome())
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_module_emit_metrics_with_outcome(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module._last_outcome = _outcome()
    metrics = module.emit_metrics(ctx, _stub_runner_outcome())
    assert metrics["checks"] == 1
    assert metrics["issues_total"] == 1


def test_module_summarize_failed_when_high_finding(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module._last_outcome = _outcome()
    findings = module.emit_findings(ctx, _stub_runner_outcome())
    metrics = module.emit_metrics(ctx, _stub_runner_outcome())
    result = module.summarize(ctx, _stub_runner_outcome(), findings, metrics)
    assert result.status == "failed"


def test_module_summarize_skipped_when_all_checks_skipped(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    module._last_outcome = _outcome(skipped=True)
    result = module.summarize(ctx, _stub_runner_outcome(), (), {})
    assert result.status == "skipped"


def test_module_summarize_incomplete_propagates(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    module = SecurityModule(ctx.config, ctx.safety_decision)
    outcome = _outcome()
    outcome = outcome.model_copy(update={"incomplete": True})
    module._last_outcome = outcome
    result = module.summarize(ctx, _stub_runner_outcome(), (), {})
    assert result.status == "incomplete"


def _stub_runner_outcome() -> RunnerOutcome:
    id_gen = IdGenerator()
    return RunnerOutcome.build(
        module_name="security",
        module_id=id_gen.new("MOD"),
        status="passed",
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(browser="chromium", browser_version="bundled", os="unknown"),
    )
