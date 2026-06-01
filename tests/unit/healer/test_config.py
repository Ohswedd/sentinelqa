"""`healer:` config block tests."""

from __future__ import annotations

import pytest
from engine.config.schema import HealerConfig, RootConfig


def test_default_healer_config_is_off() -> None:
    cfg = HealerConfig()
    assert cfg.auto_apply == "off"
    assert cfg.auto_apply_threshold == pytest.approx(0.9)


def test_healer_config_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        HealerConfig(auto_apply="reckless")  # type: ignore[arg-type]


def test_healer_config_threshold_lower_bound() -> None:
    with pytest.raises(ValueError):
        HealerConfig(auto_apply_threshold=0.3)


def test_healer_config_threshold_upper_bound() -> None:
    with pytest.raises(ValueError):
        HealerConfig(auto_apply_threshold=1.1)


def test_root_config_includes_healer() -> None:
    from engine.config.schema import ProjectConfig, TargetConfig

    cfg = RootConfig(
        project=ProjectConfig(name="x", framework="unknown", package_manager="unknown"),
        target=TargetConfig(base_url="http://localhost:3000", allowed_hosts=("localhost",)),
    )
    assert isinstance(cfg.healer, HealerConfig)
    assert cfg.healer.auto_apply == "off"
