"""Targeted unit tests filling coverage holes in the Phase-03 reporter.

Each test corresponds to a specific uncovered branch surfaced by
`make coverage` after closed. Adding them lifts the floor
margin from 95.00% to a more sustainable 95.4%+.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.dispatcher import Reporter, ReportInputs
from engine.reporter.findings_writer import write_findings
from engine.reporter.junit_writer import render_junit_xml
from engine.reporter.markdown_writer import render_markdown
from engine.reporter.sarif_rules import SarifRule, SarifRuleRegistry
from engine.reporter.sarif_writer import build_sarif_document

# Reusable fixtures (kept local — these tests intentionally don't
# depend on the per-phase `tests/conftest.py` fixtures so they exercise
# tiny one-off domain objects).


def _target() -> Target:
    return Target(base_url="https://localhost:8080", mode="safe")


def _run(status: str = "passed", finished: bool = True) -> TestRun:
    started = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
    return TestRun(
        id="RUN-GAPSAAAAAAAA",
        started_at=started,
        finished_at=started if finished else None,
        target=_target(),
        config_snapshot={},
        modules_run=(),
        status=status,  # type: ignore[arg-type]
    )


def _evidence(eid: str = "EVD-GAPSAAAAAAAA") -> Evidence:
    return Evidence(id=eid, type="screenshot", path=Path("a.png"), redacted=True)


def _finding(
    *,
    severity: str = "high",
    evidence: tuple[Evidence, ...] = (),
    location: FindingLocation | None = None,
    fid: str = "FND-GAPSAAAAAAAA",
) -> Finding:
    return Finding(
        id=fid,
        run_id="RUN-GAPSAAAAAAAA",
        module="security",
        category="security/headers",
        severity=severity,  # type: ignore[arg-type]
        confidence=0.9,
        title="Generated coverage-gap finding",
        description="Test finding for branch coverage on /api.",
        location=location or FindingLocation(),
        evidence=evidence,
        recommendation="Patch.",
        affected_target="https://localhost:8080",
        created_at=datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# findings_writer.py — naive datetime branch + reproduction_steps preserved
# ---------------------------------------------------------------------------


def test_write_findings_normalizes_naive_datetime(tmp_path: Path) -> None:
    """`generated_at` without tzinfo is coerced to UTC, not rejected."""

    naive = datetime(2026, 5, 28, 12, 0, 0)  # no tzinfo
    assert naive.tzinfo is None
    artifacts = ArtifactDirectory.create(tmp_path, "RUN-GAPSAAAAAAAA")
    written = write_findings(
        artifacts,
        (),
        run_id="RUN-GAPSAAAAAAAA",
        generated_at=naive,
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["generated_at"].endswith("+00:00")


def test_write_findings_preserves_reproduction_step_order(tmp_path: Path) -> None:
    """Reproduction steps must keep authoring order (not be sorted)."""

    f = _finding(
        evidence=(_evidence(),),
        fid="FND-REPROAAAAAAA",
    ).model_copy(update={"reproduction_steps": ("step 2", "step 1", "step 3")})
    artifacts = ArtifactDirectory.create(tmp_path, "RUN-GAPSAAAAAAAA")
    written = write_findings(
        artifacts,
        (f,),
        run_id="RUN-GAPSAAAAAAAA",
        generated_at=datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC),
    )
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["findings"][0]["reproduction_steps"] == ["step 2", "step 1", "step 3"]


# ---------------------------------------------------------------------------
# markdown_writer.py — finished_at=None branch + status-without-policy branches
# ---------------------------------------------------------------------------


def test_markdown_handles_missing_finished_at() -> None:
    """A run without finished_at renders duration as `n/a`."""

    text = render_markdown(_run(status="incomplete", finished=False))
    assert "Duration: n/a" in text


def test_markdown_release_decision_derived_from_passed_status_no_policy() -> None:
    text = render_markdown(_run(status="passed"))
    assert "Release decision:** PASS" in text


def test_markdown_release_decision_derived_from_failed_status_no_policy() -> None:
    text = render_markdown(_run(status="failed"))
    assert "Release decision:** BLOCKED" in text


def test_markdown_footer_without_html_report_path() -> None:
    text = render_markdown(_run(status="passed"), html_report_path=None)
    # No HTML report bullet rendered when html_report_path is None.
    assert "HTML report:" not in text
    # The traces/artifacts line still renders.
    assert "Traces" in text


# ---------------------------------------------------------------------------
# sarif_writer.py — file-only location + region with line + base-url fallback
# ---------------------------------------------------------------------------


def test_sarif_location_uses_file_when_present() -> None:
    finding = _finding(
        evidence=(_evidence(),),
        location=FindingLocation(file="src/app.py", line=42, route="/ignored"),
    )
    doc = build_sarif_document((finding,), _run())
    loc = doc["runs"][0]["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "src/app.py"
    assert loc["physicalLocation"]["region"]["startLine"] == 42


def test_sarif_location_falls_back_to_base_url_host() -> None:
    finding = _finding(
        evidence=(_evidence(),),
        location=FindingLocation(),  # no file, no route, no line
    )
    doc = build_sarif_document((finding,), _run())
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri.startswith("https://")
    assert "localhost" in uri


def test_sarif_location_route_without_leading_slash_is_normalized() -> None:
    finding = _finding(
        evidence=(_evidence(),),
        location=FindingLocation(route="api/users"),  # no leading slash
    )
    doc = build_sarif_document((finding,), _run())
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri.endswith("/api/users")


# ---------------------------------------------------------------------------
# sarif_rules.py — duplicate-register, clear, known_categories
# ---------------------------------------------------------------------------


def test_sarif_rule_registry_rejects_duplicate_category() -> None:
    reg = SarifRuleRegistry()
    rule = SarifRule(
        id="X-001",
        name="X",
        short_description="s",
        full_description="f",
        help_uri="https://example.com",
        category="x/y",
    )
    reg.register(rule)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(rule)


def test_sarif_rule_registry_clear_and_known_categories() -> None:
    reg = SarifRuleRegistry()
    reg.register(
        SarifRule(
            id="A-001",
            name="A",
            short_description="s",
            full_description="f",
            help_uri="u",
            category="a/x",
        )
    )
    reg.register(
        SarifRule(
            id="B-001",
            name="B",
            short_description="s",
            full_description="f",
            help_uri="u",
            category="b/x",
        )
    )
    assert tuple(reg.known_categories()) == ("a/x", "b/x")
    reg.clear()
    assert tuple(reg.known_categories()) == ()


# ---------------------------------------------------------------------------
# junit_writer.py — errored module without explicit error messages
# ---------------------------------------------------------------------------


def test_junit_errored_module_without_messages_uses_placeholder() -> None:
    """A `status="errored"` module that captured no error messages still
    emits a single `<error>` testcase with a default body."""

    mod = ModuleResult(
        id="MOD-ERRAAAAAAAAA",
        name="security",
        status="errored",
        findings=(),
        metrics={},
        duration_ms=100,
        errors=(),  # no captured messages
    )
    xml = render_junit_xml(_run(status="incomplete"), module_results=(mod,))
    root = ET.fromstring(xml)
    errors = root.findall(".//error")
    assert len(errors) == 1
    assert "module errored" in (errors[0].text or "")
    assert errors[0].get("message") == "module errored"


# ---------------------------------------------------------------------------
# dispatcher.py — score-only request, sarif registry injection
# ---------------------------------------------------------------------------


def test_dispatcher_writes_score_even_without_typed_inputs(tmp_path: Path) -> None:
    """`score.json` is requested → writer runs with null total / zero axes."""

    artifacts = ArtifactDirectory.create(tmp_path, "RUN-GAPSAAAAAAAA")
    inputs = ReportInputs(run=_run(status="incomplete"))
    outputs = Reporter().emit(inputs, artifacts, formats=["score"])
    assert "score" in outputs
    payload = json.loads(outputs["score"].read_text(encoding="utf-8"))
    assert payload["total"] is None


def test_dispatcher_accepts_custom_sarif_registry(tmp_path: Path) -> None:
    """A caller-supplied SarifRuleRegistry is used by the SARIF writer."""

    registry = SarifRuleRegistry()
    registry.register(
        SarifRule(
            id="CUSTOM-001",
            name="Custom",
            short_description="s",
            full_description="f",
            help_uri="u",
            category="security/headers",
        )
    )
    artifacts = ArtifactDirectory.create(tmp_path, "RUN-GAPSAAAAAAAA")
    inputs = ReportInputs(
        run=_run(),
        findings=(_finding(evidence=(_evidence(),)),),
    )
    outputs = Reporter(sarif_registry=registry).emit(inputs, artifacts, formats=["sarif"])
    payload = json.loads(outputs["sarif"].read_text(encoding="utf-8"))
    rule_ids = [r["id"] for r in payload["runs"][0]["tool"]["driver"]["rules"]]
    assert rule_ids == ["CUSTOM-001"]


def test_dispatcher_unknown_format_silently_ignored(tmp_path: Path) -> None:
    """Unrecognized format names are ignored (lifecycle owns validation)."""

    artifacts = ArtifactDirectory.create(tmp_path, "RUN-GAPSAAAAAAAA")
    inputs = ReportInputs(run=_run())
    outputs = Reporter().emit(inputs, artifacts, formats=["bogus", "alsoBogus"])
    # Only the canonical `run` artifact is emitted (always written).
    assert set(outputs.keys()) == {"run"}
