"""Golden agent-message shapes.

Every public exception and every entity with ``to_agent_message()`` is
pinned here so unintentional shape drift fails CI loud. Regenerate via
``make update-goldens``.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.repair_suggestion import RepairSuggestion
from engine.errors.base import (
    ConfigSchemaError,
    DependencyMissingError,
    DestructiveWithoutProofError,
    ForbiddenFlagError,
    QualityGateFailedError,
    TestExecutionError,
    UnknownHostError,
)

from sentinelqa._models import build_audit_result

GOLDEN_DIR = Path(__file__).resolve().parent / "expected"
GOLDEN_UPDATE_ENV = "SENTINELQA_UPDATE_GOLDENS"

# Fixed timestamps so goldens are byte-stable.
FIXED_TS = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)


def _dump(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _check_golden(name: str, payload: object) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / name
    actual = _dump(payload)
    if os.environ.get(GOLDEN_UPDATE_ENV):
        path.write_text(actual, encoding="utf-8")
        return
    if not path.exists():
        pytest.fail(f"missing golden {path}; run with {GOLDEN_UPDATE_ENV}=1 to create it")
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, f"golden {name} drifted; run `make update-goldens`"


def _fixed_finding() -> Finding:
    return Finding(
        id="FND-AAAAAAAAAAAA",
        run_id="RUN-AAAAAAAAAAAA",
        module="security",
        category="security/headers",
        severity="high",
        confidence=0.9,
        title="Cookie missing HttpOnly",
        description="Session cookie on /login does not set HttpOnly.",
        location=FindingLocation(route="/login"),
        evidence=(
            Evidence(
                id="EVD-AAAAAAAAAAAA",
                type="network_log",
                path=Path("traces/login.har"),
                redacted=True,
            ),
        ),
        recommendation="Set HttpOnly on the session cookie.",
        suggested_fix="Add `HttpOnly` to the Set-Cookie header.",
        affected_target="http://localhost:3000",
        reproduction_steps=("POST /login", "Inspect Set-Cookie"),
        created_at=FIXED_TS,
    )


def _fixed_repair() -> RepairSuggestion:
    return RepairSuggestion(
        id="RPR-AAAAAAAAAAAA",
        target_test="tests/sentinel/login.spec.ts",
        original="page.locator('button.signin')",
        proposed="page.getByRole('button', { name: /sign in/i })",
        confidence=0.85,
        reason="Class-based selector is brittle; semantic role + name is stable.",
        evidence=(
            Evidence(
                id="EVD-BBBBBBBBBBBB",
                type="screenshot",
                path=Path("screenshots/login.png"),
                redacted=True,
            ),
        ),
        requires_human_review=True,
    )


def test_finding_agent_message_golden() -> None:
    _check_golden("finding_high.json", _fixed_finding().to_agent_message())


def test_repair_suggestion_agent_message_golden() -> None:
    _check_golden(
        "repair_suggestion.json",
        _fixed_repair().to_agent_message(),
    )


@pytest.mark.parametrize(
    ("name", "factory"),
    [
        ("error_config_schema.json", lambda: ConfigSchemaError(detail="missing target.base_url")),
        ("error_unsafe_host.json", lambda: UnknownHostError(host="evil.example.com")),
        (
            "error_destructive.json",
            lambda: DestructiveWithoutProofError(host="staging.example.com"),
        ),
        ("error_forbidden_flag.json", lambda: ForbiddenFlagError(flag="--forbidden-example")),
        ("error_dependency.json", lambda: DependencyMissingError(dependency="playwright")),
        ("error_test_exec.json", lambda: TestExecutionError(detail="Playwright timeout")),
        ("error_quality_gate.json", lambda: QualityGateFailedError(detail="score 73 < 85")),
    ],
)
def test_exception_agent_message_golden(name, factory) -> None:
    err = factory()
    _check_golden(name, err.to_agent_message())


def test_audit_result_messages_golden() -> None:
    finding = _fixed_finding()
    result = build_audit_result(
        run_id="RUN-AAAAAAAAAAAA",
        status="failed",
        target_url="http://localhost:3000/",
        config_digest="sha256:deadbeef",
        started_at=FIXED_TS,
        finished_at=FIXED_TS,
        modules_run=("functional", "security"),
        typed_findings=(finding,),
        typed_module_results=(),
        typed_score=None,
        typed_policy=None,
        run_dir=Path("/runs/RUN-AAAAAAAAAAAA"),
    )
    _check_golden(
        "audit_result_messages.json",
        list(result.to_agent_messages()),
    )
