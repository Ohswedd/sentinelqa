"""Hypothesis property tests for the Phase 03 reporter (task 03.08).

These tests generate randomized :class:`Finding` collections and assert
that every writer:

- produces JSON / XML / SARIF that validates against its committed
  schema, and
- handles empty / single / many-finding cases without crashing.

Markers: ``slow`` so they're excluded from `make test` by default and
re-included under `make test-full` (matching the Phase 01 hypothesis
suite layout).
"""

from __future__ import annotations

import json
import string
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import jsonschema
import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.findings_writer import write_findings
from engine.reporter.junit_writer import render_junit_xml
from engine.reporter.sarif_writer import build_sarif_document
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]
FINDINGS_SCHEMA = REPO_ROOT / "packages" / "shared-schema" / "findings.schema.json"
SARIF_SCHEMA = REPO_ROOT / "packages" / "shared-schema" / "external" / "sarif-2.1.0.json"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _id_strategy(prefix: str) -> st.SearchStrategy[str]:
    """SentinelQA IDs: `<PREFIX>-<12 [A-Z0-9]>`."""

    return st.from_regex(rf"^{prefix}-[A-Z0-9]{{12}}$", fullmatch=True)


_severity_strategy = st.sampled_from(("critical", "high", "medium", "low", "info"))

_evidence_strategy: st.SearchStrategy[Evidence] = st.builds(
    Evidence,
    id=_id_strategy("EVD"),
    type=st.sampled_from(
        (
            "screenshot",
            "video",
            "trace",
            "har",
            "console_log",
            "network_log",
            "dom_snapshot",
            "stack_trace",
            "api_sample",
            "source_ref",
        )
    ),
    path=st.builds(
        Path, st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=80)
    ),
    redacted=st.just(True),
)


def _finding_strategy(run_id: str, severity: Severity | None = None) -> st.SearchStrategy[Finding]:
    sev_strategy = st.just(severity) if severity is not None else _severity_strategy

    def _build(
        fid: str,
        sev: Severity,
        title: str,
        description: str,
        confidence: float,
        evidence_count: int,
        route: str | None,
    ) -> Finding:
        # Drop the title's leading/trailing whitespace because Pydantic
        # strips it and we want descriptions to remain non-empty.
        title = title.strip() or "Generated finding"
        description = description.strip() or "Generated description."
        # Build evidence: medium+ requires at least one.
        ev_min = 1 if sev in ("critical", "high", "medium") else 0
        n = max(ev_min, min(evidence_count, 3))
        # Generate distinct evidence ids deterministically from fid.
        evs = tuple(
            Evidence(
                id=f"EVD-{i:012X}".replace("0", "A"),  # crude but valid
                type="screenshot",
                path=Path(f"evidence/{i}.png"),
                redacted=True,
            )
            for i in range(1, n + 1)
        )
        return Finding(
            id=fid,
            run_id=run_id,
            module="generated",
            category="generated/test",
            severity=sev,
            confidence=round(confidence, 4),
            title=title,
            description=description,
            location=FindingLocation(route=route),
            evidence=evs,
            recommendation="Generated recommendation.",
            affected_target="http://localhost:3000",
            created_at=datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC),
        )

    # Constrain text to printable ASCII so generated payloads are
    # XML-valid (JUnit writer) and JSON-stable. Real findings always
    # pass through the redaction layer before any non-printable bytes
    # could land here.
    safe_text = st.text(
        alphabet=string.ascii_letters + string.digits + " /:-_.,",
        min_size=8,
        max_size=120,
    ).filter(lambda s: s.strip() != "")
    safe_desc = st.text(
        alphabet=string.ascii_letters + string.digits + " /:-_.,",
        min_size=4,
        max_size=400,
    ).filter(lambda s: s.strip() != "")
    return st.builds(
        _build,
        fid=_id_strategy("FND"),
        sev=sev_strategy,
        title=safe_text,
        description=safe_desc,
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        evidence_count=st.integers(min_value=0, max_value=3),
        route=st.one_of(st.none(), st.just("/"), st.just("/login"), st.just("/api/v1/users")),
    )


def _findings_list(run_id: str) -> st.SearchStrategy[tuple[Finding, ...]]:
    return st.lists(_finding_strategy(run_id), min_size=0, max_size=5).map(tuple)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixture_run() -> TestRun:
    return TestRun(
        id="RUN-PROPERTYTEST",
        started_at=datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC),
        target=Target(base_url="http://localhost:3000", mode="safe"),
        config_snapshot={"version": 1},
        modules_run=(),
        status="passed",
    )


def _load_schema(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(_findings_list("RUN-PROPERTYTEST"))
@settings(
    deadline=None,
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_findings_writer_always_validates(
    findings: Sequence[Finding],
) -> None:
    schema = _load_schema(FINDINGS_SCHEMA)
    with tempfile.TemporaryDirectory(prefix="sentinelqa-property-") as tmp:
        artifacts = ArtifactDirectory.create(Path(tmp), "RUN-PROPERTYTEST")
        written = write_findings(
            artifacts,
            findings,
            run_id="RUN-PROPERTYTEST",
            generated_at=datetime(2026, 5, 27, 12, 0, 30, tzinfo=UTC),
            enforce_evidence=False,
        )
        payload = json.loads(written.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


@given(_findings_list("RUN-PROPERTYTEST"))
@settings(
    deadline=None,
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_junit_writer_always_emits_parseable_xml(
    findings: Sequence[Finding],
) -> None:
    xml = render_junit_xml(_fixture_run(), findings=tuple(findings))
    # Will raise on malformed XML; we just need the parse to succeed.
    root = ET.fromstring(xml)
    assert root.tag == "testsuites"


@given(_findings_list("RUN-PROPERTYTEST"))
@settings(
    deadline=None,
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_sarif_writer_always_validates(
    findings: Sequence[Finding],
) -> None:
    doc = build_sarif_document(tuple(findings), _fixture_run())
    schema = _load_schema(SARIF_SCHEMA)
    validator = jsonschema.Draft4Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    assert errors == [], "\n".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)
