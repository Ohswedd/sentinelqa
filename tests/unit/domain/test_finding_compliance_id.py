"""Finding ``compliance_id`` field — additive v2 extension."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from engine.domain import Finding, IdGenerator
from engine.domain.schema import FINDINGS_SCHEMA_VERSION

GEN = IdGenerator()


def _base_kwargs() -> dict:
    return {
        "id": GEN.new("FND"),
        "run_id": GEN.new("RUN"),
        "module": "compliance",
        "category": "gdpr.cookies_before_consent",
        "severity": "high",
        "confidence": 0.95,
        "title": "Automated GDPR check found: cookies set before consent",
        "description": "Set-Cookie observed on first load before banner accept.",
        "created_at": datetime.now(UTC),
    }


def test_compliance_id_field_accepts_wcag_22_tag() -> None:
    f = Finding(**_base_kwargs(), compliance_id="wcag-2.2:target-size-min")
    assert f.compliance_id == "wcag-2.2:target-size-min"
    payload = f.to_dict()
    assert payload["compliance_id"] == "wcag-2.2:target-size-min"
    assert payload["schema_version"] == FINDINGS_SCHEMA_VERSION


def test_compliance_id_field_accepts_gdpr_article() -> None:
    f = Finding(**_base_kwargs(), compliance_id="gdpr:Art.6")
    assert f.compliance_id == "gdpr:Art.6"


def test_compliance_id_field_accepts_edpb_guidance() -> None:
    f = Finding(**_base_kwargs(), compliance_id="gdpr:EDPB-03/2022")
    assert f.compliance_id == "gdpr:EDPB-03/2022"


def test_compliance_id_defaults_to_none() -> None:
    f = Finding(**_base_kwargs())
    assert f.compliance_id is None
    assert f.to_dict()["compliance_id"] is None


def test_compliance_id_rejects_uppercase_regime() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), compliance_id="GDPR:Art.6")


def test_compliance_id_rejects_missing_separator() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), compliance_id="gdpr-Art-6")


def test_compliance_id_rejects_empty_rule() -> None:
    with pytest.raises(ValueError):
        Finding(**_base_kwargs(), compliance_id="gdpr:")
