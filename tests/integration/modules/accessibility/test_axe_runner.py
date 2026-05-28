"""Integration test for the axe-core output translation (Phase 11.02).

The TS subcommand (``sentinel-ts audit-a11y``) serialises axe-core's
``result.violations`` verbatim into the per-route JSON artifact. This
test verifies that the Python translation in
:mod:`modules.accessibility.axe_runner` + the findings normaliser
correctly converts:

- A compliant fixture (``tests/fixtures/a11y/compliant_axe_output.json``)
  → zero typed violations + zero findings.
- A non-compliant fixture (``tests/fixtures/a11y/broken_axe_output.json``)
  → typed violations with the expected rule IDs + matching findings.

The expected rule IDs in the broken fixture mirror what axe-core 4.x
reports against ``packages/ts-runtime/fixtures/a11y/broken.html``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.ids import IdGenerator

from modules.accessibility.axe_runner import axe_violations_from_payload
from modules.accessibility.findings import findings_from_page
from modules.accessibility.models import A11yPageResult

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "a11y"

EXPECTED_BROKEN_RULES = frozenset(
    {
        "html-has-lang",
        "document-title",
        "image-alt",
        "button-name",
        "link-name",
        "color-contrast",
        "label",
    }
)


@pytest.fixture(scope="module")
def compliant_payload() -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / "compliant_axe_output.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.fixture(scope="module")
def broken_payload() -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / "broken_axe_output.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _build_page(route: str, payload: dict[str, object]) -> A11yPageResult:
    violations = axe_violations_from_payload(payload)
    return A11yPageResult(
        route=route,
        url=f"http://localhost:3000{route}",
        fetched_at="2026-05-28T00:00:00+00:00",
        axe_violations=violations,
        duration_ms=10,
    )


def test_compliant_fixture_yields_zero_violations(
    compliant_payload: dict[str, object],
) -> None:
    violations = axe_violations_from_payload(compliant_payload)
    assert violations == ()


def test_broken_fixture_yields_expected_rule_ids(
    broken_payload: dict[str, object],
) -> None:
    violations = axe_violations_from_payload(broken_payload)
    assert {v.rule_id for v in violations} == EXPECTED_BROKEN_RULES


def test_severity_mapping_for_broken_fixture(
    broken_payload: dict[str, object],
) -> None:
    page = _build_page("/", broken_payload)
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    severities = {f.category: f.severity for f in findings}
    assert severities["a11y.image-alt"] == "high"  # critical → high
    assert severities["a11y.label"] == "high"
    assert severities["a11y.color-contrast"] == "high"  # serious → high


def test_no_wcag_compliance_claims_in_findings(
    broken_payload: dict[str, object],
) -> None:
    page = _build_page("/", broken_payload)
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
        now=datetime(2026, 5, 28, tzinfo=UTC),
    )
    for finding in findings:
        assert "fully WCAG" not in finding.description
        assert "WCAG compliant" not in finding.description
        assert "fully WCAG" not in finding.title
        assert "WCAG compliant" not in finding.title
        # Expected language is always "Automated accessibility check found".
        assert finding.title.startswith("Automated accessibility check found")


def test_help_url_propagates_to_finding(broken_payload: dict[str, object]) -> None:
    page = _build_page("/", broken_payload)
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    image_alt = next(f for f in findings if f.category == "a11y.image-alt")
    assert "dequeuniversity.com" in image_alt.description


def test_experimental_rules_lower_confidence() -> None:
    payload = {
        "violations": [
            {
                "id": "scrollable-region-focusable",
                "impact": "moderate",
                "tags": ["wcag2aa", "experimental"],
                "help": "Scrollable region must have keyboard access",
                "helpUrl": "",
                "description": "",
                "nodes": [{"target": ["div"], "html": "<div>"}],
            }
        ]
    }
    page = _build_page("/", payload)
    findings = findings_from_page(
        page=page,
        run_id="RUN-AAAAAAAAAAAA",
        target_base_url="http://localhost:3000",
        id_generator=IdGenerator(),
    )
    assert len(findings) == 1
    assert findings[0].confidence == pytest.approx(0.6)
