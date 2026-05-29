"""Unit coverage for the ApiModule internals (option parsing, helpers, dispatch)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.schema import ApiConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl

from modules.api.findings import findings_from_checks
from modules.api.models import (
    API_RESULT_SCHEMA_VERSION,
    ApiCheckResult,
    ApiIssue,
)
from modules.api.module import (
    ApiModule,
    _coerce_path,
    _coerce_str,
    _coerce_str_tuple,
    _read_options,
    _resolve_enabled_checks,
    _skip_result,
)
from modules.api.options import ApiModuleOptions


def _root_config(**api_overrides: Any) -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl("http://127.0.0.1:8000"), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(**api_overrides),
    )


def _ctx(tmp_path: Path, config: RootConfig, options: Any) -> ModuleContext:
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-COVERAGE001A")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    return ModuleContext(
        module_name="api",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="test",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-COVERAGE001A",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": options},
    )


def test_coerce_str_tuple_handles_str_list_tuple_and_none() -> None:
    assert _coerce_str_tuple(None) == ()
    assert _coerce_str_tuple("a") == ("a",)
    assert _coerce_str_tuple(["a", "b"]) == ("a", "b")
    assert _coerce_str_tuple(("a", "b")) == ("a", "b")
    assert _coerce_str_tuple(42) == ()  # unsupported type → empty


def test_coerce_path_accepts_str_and_path() -> None:
    p = Path("/tmp/x")
    assert _coerce_path(None) is None
    assert _coerce_path(p) is p
    assert _coerce_path("/tmp/y") == Path("/tmp/y")


def test_coerce_str_handles_blanks() -> None:
    assert _coerce_str(None) is None
    assert _coerce_str("   ") is None
    assert _coerce_str(" a ") == "a"


def test_read_options_from_dict(tmp_path: Path) -> None:
    config = _root_config()
    ctx = _ctx(
        tmp_path,
        config,
        {
            "routes": ["/x"],
            "openapi_path": str(tmp_path / "a.json"),
            "graphql_path": tmp_path / "b.graphql",
            "discovery_path": str(tmp_path / "d.json"),
            "enabled_checks": ["contract"],
            "diff_since_run_id": "RUN-PREV",
            "artifacts_root": tmp_path / "artifacts",
        },
    )
    opts = _read_options(ctx)
    assert opts.routes == ("/x",)
    assert opts.openapi_path == tmp_path / "a.json"
    assert opts.graphql_path == tmp_path / "b.graphql"
    assert opts.diff_since_run_id == "RUN-PREV"
    assert opts.enabled_checks == ("contract",)
    assert opts.artifacts_root == tmp_path / "artifacts"


def test_read_options_accepts_already_typed_options(tmp_path: Path) -> None:
    typed = ApiModuleOptions(routes=("/x",))
    config = _root_config()
    ctx = _ctx(tmp_path, config, typed)
    parsed = _read_options(ctx)
    assert parsed is typed


def test_read_options_with_flat_dict(tmp_path: Path) -> None:
    config = _root_config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-FLAT")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    ctx = ModuleContext(
        module_name="api",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="t",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-FLAT",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"routes": ["/r"]},  # flat dict, no 'api' namespace
    )
    opts = _read_options(ctx)
    assert opts.routes == ("/r",)


def test_read_options_empty_returns_defaults(tmp_path: Path) -> None:
    config = _root_config()
    artifacts = ArtifactDirectory.create(tmp_path, run_id="RUN-EMPTY")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    ctx = ModuleContext(
        module_name="api",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="t",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-EMPTY",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": "unsupported-string"},  # not a dict / dataclass → defaults
    )
    opts = _read_options(ctx)
    assert opts == ApiModuleOptions()


def test_resolve_enabled_checks_intersects_with_config() -> None:
    config = _root_config(enabled_checks=("contract", "negative"))
    requested = ApiModuleOptions(enabled_checks=("contract", "auth"))  # auth not configured
    enabled = _resolve_enabled_checks(config, requested)
    assert enabled == ("contract",)


def test_resolve_enabled_checks_returns_config_when_options_empty() -> None:
    config = _root_config(enabled_checks=("contract", "negative"))
    requested = ApiModuleOptions()
    assert _resolve_enabled_checks(config, requested) == ("contract", "negative")


def test_skip_result_marks_skipped() -> None:
    skip = _skip_result("contract", "no doc supplied")
    assert skip.skipped is True
    assert skip.skip_reason == "no doc supplied"
    assert skip.issues == ()
    assert skip.check == "contract"


def test_module_emit_findings_translates_issues(tmp_path: Path) -> None:
    config = _root_config()
    ctx = _ctx(tmp_path, config, {})
    ApiModule(config, ctx.safety_decision)  # constructor is exercised
    issue = ApiIssue(
        rule_id="CONTRACT-SCHEMA",
        severity="high",
        confidence=0.9,
        title="t",
        description="d",
        method="GET",
        route="/x",
        recommendation="r",
        evidence={"k": "v"},
    )
    findings = findings_from_checks(
        checks=(
            ApiCheckResult(
                schema_version=API_RESULT_SCHEMA_VERSION,
                check="contract",
                issues=(issue,),
                targets_scanned=1,
                duration_ms=1,
            ),
        ),
        run_id=ctx.run_id,
        target_base_url=str(ctx.target.base_url),
        id_generator=ctx.id_generator,
    )
    assert len(findings) == 1
    assert findings[0].module == "api"
    assert findings[0].category.startswith("api/contract/")
    assert findings[0].severity == "high"


def test_module_run_persists_artifacts(tmp_path: Path) -> None:
    config = _root_config()
    ctx = _ctx(tmp_path, config, {})
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.name == "api"
    api_dir = ctx.run_dir / "api"
    assert (api_dir / "index.json").exists()
    # No api-schema.json should exist because no OpenAPI / GraphQL doc was supplied.
    assert not (api_dir / "api-schema.json").exists()


def test_module_metrics_include_check_counts(tmp_path: Path) -> None:
    config = _root_config()
    ctx = _ctx(tmp_path, config, {})
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    metrics = result.metrics
    assert "checks" in metrics
    assert metrics["checks"] >= 1
    assert metrics["openapi_loaded"] == 0
    assert metrics["graphql_loaded"] == 0


def test_lifecycle_hooks_return_defaults_when_not_yet_run(tmp_path: Path) -> None:
    """collect_evidence / emit_findings / emit_metrics short-circuit when
    _run_audit hasn't populated _last_outcome (defensive null-guards)."""

    from engine.runner.results import EnvironmentContext, RunnerOutcome

    config = _root_config()
    ctx = _ctx(tmp_path, config, {})
    module = ApiModule(config, ctx.safety_decision)
    fake_outcome = RunnerOutcome.build(
        module_name="api",
        module_id="MOD-XXXXXXXXXXXX",
        status="skipped",
        tests=(),
        duration_ms=0,
        environment=EnvironmentContext(browser="chromium", browser_version="x", os="x"),
    )
    # Module has not run yet, so the helpers should return safe defaults.
    assert module.collect_evidence(ctx, fake_outcome) == ()
    assert module.emit_findings(ctx, fake_outcome) == ()
    assert module.emit_metrics(ctx, fake_outcome) == {"checks": 0}
