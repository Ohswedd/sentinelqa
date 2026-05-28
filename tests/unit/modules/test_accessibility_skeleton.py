"""Unit tests for :mod:`modules.accessibility` (Phase 11.01)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext, SentinelModule
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.orchestrator.registry import ModuleRegistry
from engine.policy.safety import SafetyDecision

from modules.accessibility import (
    AccessibilityModule,
    AccessibilityModuleOptions,
    register_with_default_registry,
)
from modules.accessibility.models import (
    A11yPageResult,
    AxeNode,
    AxeViolation,
    KeyboardIssue,
    LandmarkIssue,
)
from modules.accessibility.module import _factory
from modules.accessibility.runner import A11yInvocation, A11yRunnerError, StubA11yRunner


def _write_config(
    root: Path,
    *,
    base_url: str = "http://localhost:3000",
    accessibility_block: str = "",
) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\n"
        "project:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n  allowed_hosts: [localhost, 127.0.0.1]\n"
        + accessibility_block,
        encoding="utf-8",
    )
    return p


def _build_ctx(
    tmp_path: Path,
    *,
    base_url: str = "http://localhost:3000",
    options: Mapping[str, Any] | None = None,
    accessibility_block: str = "",
) -> ModuleContext:
    config_path = _write_config(
        tmp_path, base_url=base_url, accessibility_block=accessibility_block
    )
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
        module_name="accessibility",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=artifacts_root,
        target=target,
        id_generator=IdGenerator(),
        options=options or {},
    )


def _violation(rule_id: str, impact: str = "serious") -> AxeViolation:
    return AxeViolation(
        rule_id=rule_id,
        impact=impact,  # type: ignore[arg-type]
        help=f"{rule_id} help",
        help_url=f"https://example.test/{rule_id}",
        description=f"{rule_id} desc",
        tags=("wcag2aa",),
        nodes=(AxeNode(target=(f"button.{rule_id}",), html=f"<button class='{rule_id}'/>"),),
    )


def _page(
    route: str = "/",
    *,
    violations: tuple[AxeViolation, ...] = (),
    keyboard: tuple[KeyboardIssue, ...] = (),
    landmarks: tuple[LandmarkIssue, ...] = (),
) -> A11yPageResult:
    return A11yPageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=violations,
        keyboard_issues=keyboard,
        landmark_issues=landmarks,
        duration_ms=42,
    )


# ---------------------------------------------------------------------------
# Module class basics
# ---------------------------------------------------------------------------


def test_accessibility_module_is_sentinel_module(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = AccessibilityModule(ctx.config, ctx.safety_decision)
    assert isinstance(module, SentinelModule)
    assert AccessibilityModule.name == "accessibility"


def test_factory_returns_accessibility_module_instance(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    instance = _factory(ctx.config, ctx.safety_decision)
    assert isinstance(instance, AccessibilityModule)


def test_validate_prerequisites_is_noop(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = AccessibilityModule(ctx.config, ctx.safety_decision)
    module.validate_prerequisites(ctx)  # no exception


def test_plan_returns_empty_routes_are_resolved_in_execute(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    module = AccessibilityModule(ctx.config, ctx.safety_decision)
    assert module.plan(ctx) == ()


# ---------------------------------------------------------------------------
# Run orchestration (stub runner)
# ---------------------------------------------------------------------------


def test_run_with_no_routes_skips(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=())
    ctx = _build_ctx(tmp_path)
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    # No CLI/discovery/config-driven routes → the module short-circuits
    # without spawning the runner. `sentinel a11y` (not audit) injects
    # the ("/",) fallback explicitly.
    assert runner.invocation is None
    assert result.status == "skipped"


def test_run_with_compliant_page_passes(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),))
    ctx = _build_ctx(tmp_path, options={"accessibility": {"routes": ("/",)}})
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "passed"
    assert result.findings == ()
    assert result.metrics["pages"] == 1
    assert result.metrics["total_issues"] == 0


def test_run_with_violations_emits_findings(tmp_path: Path) -> None:
    page = _page(violations=(_violation("color-contrast", impact="serious"),))
    runner = StubA11yRunner(pages=(page,))
    ctx = _build_ctx(tmp_path, options={"accessibility": {"routes": ("/",)}})
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "failed"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.module == "accessibility"
    assert finding.severity == "high"
    assert "WCAG compliant" not in finding.description
    assert "WCAG compliant" not in finding.title


def test_incomplete_run_translates_to_incomplete_status(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),), incomplete=True)
    ctx = _build_ctx(tmp_path, options={"accessibility": {"routes": ("/",)}})
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert result.status == "incomplete"


def test_runner_error_bubbles_up_for_orchestrator(tmp_path: Path) -> None:
    class _Boom:
        def run(self, _: A11yInvocation) -> Any:
            raise A11yRunnerError("sentinel-ts missing")

    ctx = _build_ctx(tmp_path, options={"accessibility": {"routes": ("/",)}})
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: _Boom()
    )
    with pytest.raises(A11yRunnerError):
        module.run(ctx)


# ---------------------------------------------------------------------------
# Options resolution
# ---------------------------------------------------------------------------


def test_options_dict_routes_string_normalised(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),))
    ctx = _build_ctx(
        tmp_path,
        options={"accessibility": {"routes": "/dashboard"}},
    )
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/dashboard",)


def test_options_dict_routes_list(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=())
    ctx = _build_ctx(
        tmp_path,
        options={"accessibility": {"routes": ["/", "/dashboard", "settings"]}},
    )
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/", "/dashboard", "/settings")


def test_options_typed_dataclass_round_trip(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),))
    opts = AccessibilityModuleOptions(routes=("/profile",), axe_tags=("wcag2a",))
    ctx = _build_ctx(tmp_path, options={"accessibility": opts})
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/profile",)
    assert runner.invocation.axe_tags == ("wcag2a",)


def test_options_dict_discovery_path_drives_routes(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=())
    discovery = tmp_path / "discovery.json"
    discovery.write_text(
        '{"routes": [{"path": "/"}, {"path": "/dashboard"}, "/settings", "/"]}',
        encoding="utf-8",
    )
    ctx = _build_ctx(
        tmp_path,
        options={"accessibility": {"discovery_path": str(discovery)}},
    )
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    # Order preserved, duplicates removed.
    assert runner.invocation.routes == ("/", "/dashboard", "/settings")


def test_options_dict_discovery_path_missing_falls_back_to_skip(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=())
    ctx = _build_ctx(
        tmp_path,
        options={"accessibility": {"discovery_path": tmp_path / "nope.json"}},
    )
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    result = module.run(ctx)
    assert runner.invocation is None
    assert result.status == "skipped"


def test_options_dict_axe_tags_overrides_config(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),))
    ctx = _build_ctx(
        tmp_path,
        options={"accessibility": {"routes": ("/",), "axe_tags": ("wcag21aa",)}},
    )
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.axe_tags == ("wcag21aa",)


def test_config_routes_used_when_options_omit_them(tmp_path: Path) -> None:
    runner = StubA11yRunner(pages=(_page(),))
    block = "\naccessibility:\n  routes:\n    - /\n    - /profile\n"
    ctx = _build_ctx(tmp_path, accessibility_block=block)
    module = AccessibilityModule(
        ctx.config, ctx.safety_decision, runner_factory=lambda _c, _s: runner
    )
    module.run(ctx)
    assert runner.invocation is not None
    assert runner.invocation.routes == ("/", "/profile")


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def test_register_with_default_registry_is_idempotent() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    register_with_default_registry(registry)
    assert "accessibility" in registry.modules


def test_register_with_explicit_registry_records_factory() -> None:
    registry = ModuleRegistry()
    register_with_default_registry(registry)
    factory = registry.modules["accessibility"]
    assert factory is _factory
