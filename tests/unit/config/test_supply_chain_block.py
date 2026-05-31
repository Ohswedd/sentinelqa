"""Strict validation for the `policy.supply_chain:` config block (Phase 33, ADR-0045)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.config.schema import (
    PolicyConfig,
    SupplyChainConfig,
    SupplyChainContainerConfig,
    SupplyChainLicensesConfig,
    SupplyChainOsvConfig,
    SupplyChainSbomConfig,
)
from pydantic import ValidationError


def test_defaults_match_phase_33_readme() -> None:
    cfg = SupplyChainConfig()
    assert cfg.max_lockfile_age_days == 180
    assert cfg.sbom.enabled is True
    assert cfg.osv.enabled is True
    assert cfg.osv.api_base == "https://api.osv.dev"
    assert cfg.osv.rate_limit_rps == 5.0
    assert cfg.container.image is None
    assert cfg.container.max_findings == 200
    assert "Apache-2.0" in cfg.licenses.allow
    assert "AGPL-3.0-only" in cfg.licenses.deny
    assert cfg.licenses.unknown_severity == "low"


def test_policy_config_carries_supply_chain_subblock() -> None:
    policy = PolicyConfig()
    assert isinstance(policy.supply_chain, SupplyChainConfig)


def test_load_config_accepts_supply_chain_block(tmp_path: Path) -> None:
    config = tmp_path / "sentinel.config.yaml"
    config.write_text(
        "version: 1\n"
        "project:\n  name: t\n"
        "target:\n  base_url: http://localhost:8088\n  allowed_hosts: [localhost]\n"
        "policy:\n"
        "  supply_chain:\n"
        "    max_lockfile_age_days: 90\n"
        "    osv:\n"
        "      enabled: false\n"
        "    container:\n"
        "      image: example:tag\n"
        "      max_findings: 50\n"
        "    licenses:\n"
        "      allow: [MIT, Apache-2.0]\n"
        "      deny: [GPL-3.0-only]\n"
        "      unknown_severity: medium\n",
        encoding="utf-8",
    )
    root = load_config(config)
    sc = root.policy.supply_chain
    assert sc.max_lockfile_age_days == 90
    assert sc.osv.enabled is False
    assert sc.container.image == "example:tag"
    assert sc.container.max_findings == 50
    assert sc.licenses.allow == ("MIT", "Apache-2.0")
    assert sc.licenses.deny == ("GPL-3.0-only",)
    assert sc.licenses.unknown_severity == "medium"


def test_max_lockfile_age_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SupplyChainConfig(max_lockfile_age_days=0)


def test_osv_rate_limit_bounded() -> None:
    with pytest.raises(ValidationError):
        SupplyChainOsvConfig(rate_limit_rps=0.0)
    with pytest.raises(ValidationError):
        SupplyChainOsvConfig(rate_limit_rps=1000.0)


def test_container_max_findings_bounded() -> None:
    with pytest.raises(ValidationError):
        SupplyChainContainerConfig(max_findings=0)
    with pytest.raises(ValidationError):
        SupplyChainContainerConfig(max_findings=100_000)


def test_unknown_severity_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        SupplyChainLicensesConfig(unknown_severity="critical")  # type: ignore[arg-type]


def test_supply_chain_block_forbids_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        SupplyChainConfig.model_validate({"sneaky_field": True})


def test_sbom_config_default_enabled() -> None:
    assert SupplyChainSbomConfig().enabled is True
