"""Pydantic schema tests for sentinel.config.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.config.schema import RootConfig
from pydantic import ValidationError


def _minimal_dict() -> dict:
    return {
        "version": 1,
        "project": {"name": "demo", "framework": "nextjs", "package_manager": "pnpm"},
        "target": {"base_url": "http://localhost:3000", "allowed_hosts": ["localhost"]},
    }


def test_minimal_config_validates() -> None:
    cfg = RootConfig.model_validate(_minimal_dict())
    assert cfg.project.name == "demo"
    assert cfg.security.mode == "safe"  # default applied


def test_unknown_key_rejected() -> None:
    bad = _minimal_dict()
    bad["evil_extra"] = True
    with pytest.raises(ValidationError):
        RootConfig.model_validate(bad)


def test_wildcard_host_rejected() -> None:
    bad = _minimal_dict()
    bad["target"]["allowed_hosts"] = ["*.example.com"]
    with pytest.raises(ValidationError):
        RootConfig.model_validate(bad)


def test_destructive_requires_proof() -> None:
    bad = _minimal_dict()
    bad["security"] = {"mode": "authorized_destructive", "destructive_tests": True}
    with pytest.raises(ValidationError):
        RootConfig.model_validate(bad)


def test_destructive_with_proof_ok() -> None:
    ok = _minimal_dict()
    ok["security"] = {"mode": "authorized_destructive", "destructive_tests": True}
    ok["target"]["proof_of_authorization"] = "./.sentinel/proof.yaml"
    cfg = RootConfig.model_validate(ok)
    assert cfg.target.proof_of_authorization == Path("./.sentinel/proof.yaml")


def test_min_quality_score_bounds() -> None:
    bad = _minimal_dict()
    bad["policy"] = {"min_quality_score": 101}
    with pytest.raises(ValidationError):
        RootConfig.model_validate(bad)


def test_negative_budget_rejected() -> None:
    bad = _minimal_dict()
    bad["performance"] = {"budgets": {"lcp_ms": -1}}
    with pytest.raises(ValidationError):
        RootConfig.model_validate(bad)


def test_modules_default_picks_safe_defaults() -> None:
    cfg = RootConfig.model_validate(_minimal_dict())
    assert cfg.modules.chaos is False
    assert cfg.modules.functional is True
