"""Unit tests for engine.ci.modes."""

from __future__ import annotations

import pytest
from engine.ci.modes import (
    CI_MODES,
    DEFAULT_CI_MODE,
    InvalidCiModeError,
    apply_mode,
    grep_for_mode,
    mode_plan,
)
from engine.config.schema import (
    ModulesConfig,
    PolicyConfig,
    ProjectConfig,
    RootConfig,
    TargetConfig,
)


def _config(
    *,
    modules: ModulesConfig | None = None,
    policy: PolicyConfig | None = None,
) -> RootConfig:
    return RootConfig(
        project=ProjectConfig(name="ex"),
        target=TargetConfig(
            base_url="http://localhost:3000",
            allowed_hosts=("localhost",),
        ),
        modules=modules or ModulesConfig(),
        policy=policy or PolicyConfig(),
    )


def test_constants_present() -> None:
    assert "fast" in CI_MODES
    assert "release" in CI_MODES
    assert DEFAULT_CI_MODE == "standard"
    assert len(CI_MODES) == 5


def test_grep_for_mode_matches_phase_10() -> None:
    assert grep_for_mode("fast") == "@p0"
    assert grep_for_mode("standard") == "@p0|@p1"
    assert grep_for_mode("full") is None
    assert grep_for_mode("nightly") is None
    assert grep_for_mode("release") is None


def test_invalid_mode_raises() -> None:
    with pytest.raises(InvalidCiModeError):
        mode_plan("bogus", config=_config())  # type: ignore[arg-type]
    with pytest.raises(InvalidCiModeError):
        apply_mode(_config(), mode="bogus")  # type: ignore[arg-type]


def test_fast_mode_is_p0_smoke() -> None:
    plan = mode_plan("fast", config=_config())
    assert plan.mode == "fast"
    assert plan.grep == "@p0"
    # functional + security present (intersection with defaults)
    assert "functional" in plan.modules
    assert "security" in plan.modules
    # a11y NOT in fast
    assert "accessibility" not in plan.modules


def test_standard_mode_is_p0_p1() -> None:
    plan = mode_plan("standard", config=_config())
    assert plan.grep == "@p0|@p1"
    assert "functional" in plan.modules
    assert "accessibility" in plan.modules
    assert "security" in plan.modules


def test_full_mode_runs_every_enabled_module_no_grep() -> None:
    cfg = _config(modules=ModulesConfig(visual=True))
    plan = mode_plan("full", config=cfg)
    assert plan.grep is None
    assert "functional" in plan.modules
    assert "visual" in plan.modules
    assert "performance" in plan.modules


def test_nightly_force_enables_chaos_even_if_disabled() -> None:
    cfg = _config(modules=ModulesConfig(chaos=False))
    plan = mode_plan("nightly", config=cfg)
    assert plan.grep is None
    assert "chaos" in plan.modules
    assert plan.extras["extended_security"] is True


def test_release_mode_raises_min_quality_score() -> None:
    cfg = _config(policy=PolicyConfig(min_quality_score=80))
    plan = mode_plan("release", config=cfg)
    assert plan.policy_overrides.get("min_quality_score") == 90


def test_release_keeps_stricter_user_floor() -> None:
    cfg = _config(policy=PolicyConfig(min_quality_score=95))
    plan = mode_plan("release", config=cfg)
    assert plan.policy_overrides == {}, "stricter user floor must not be relaxed"


def test_apply_mode_returns_unchanged_config_when_no_overrides() -> None:
    cfg = _config()
    effective, plan = apply_mode(cfg, mode="full")
    assert effective is cfg
    assert plan.mode == "full"


def test_apply_mode_release_overrides_min_quality_score() -> None:
    cfg = _config(policy=PolicyConfig(min_quality_score=70))
    effective, _ = apply_mode(cfg, mode="release")
    assert effective.policy.min_quality_score == 90
    # original config unchanged (immutability)
    assert cfg.policy.min_quality_score == 70


def test_apply_mode_fail_under_wins_over_mode_default() -> None:
    cfg = _config(policy=PolicyConfig(min_quality_score=70))
    # fail_under is authoritative — even in release mode.
    effective, _ = apply_mode(cfg, mode="release", fail_under=75)
    assert effective.policy.min_quality_score == 75


def test_fast_mode_intersects_with_config_disabled_modules() -> None:
    cfg = _config(modules=ModulesConfig(security=False))
    plan = mode_plan("fast", config=cfg)
    # security disabled in config → must not be in fast plan even though
    # the preset wants it (config is authoritative — CLAUDE §17).
    assert "security" not in plan.modules


def test_modeplan_to_dict_roundtrip() -> None:
    plan = mode_plan("nightly", config=_config())
    data = plan.to_dict()
    assert data["mode"] == "nightly"
    assert isinstance(data["modules"], list)
    assert data["extras"] == {"extended_security": True}
    assert data["grep"] is None
