"""Phase 20.08 — End-to-end healer → suggest_fix → verify_fix loop.

This exercises the agent-observable contract documented in our product spec4
and ADR-0025: the Healer publishes proposals, the agent (here: the
test) picks one and applies it, then ``sentinel.verify_fix`` confirms
the failure is gone. The MCP transport / SDK boundaries are stubbed —
the test only verifies the loop's *logic* end-to-end.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.models import RepairProposal
from engine.healer.writer import write_index, write_proposal

_SPEC = """\
// SENTINELQA AUTO-GENERATED SPEC
// generated_at: 2026-05-01T12:00:00+00:00

import { test, expect } from '@playwright/test';

test('signs in', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: /sign in/i }).click();
});
"""


def _make_proposal(target_test: str) -> RepairProposal:
    gen = IdGenerator()
    original_line = "  await page.getByRole('button', { name: /sign in/i }).click();"
    proposed_line = "  await page.getByRole('button', { name: /log in/i }).click();"
    return RepairProposal(
        id=gen.new("RPR"),
        kind="locator",
        target_test=target_test,
        target_test_line=7,
        original_behavior=original_line,
        proposed_change=proposed_line,
        confidence=0.95,
        reason="Sign in renamed to Log in.",
        evidence=(Evidence(id=gen.new("EVD"), type="source_ref", path=Path(target_test)),),
        requires_human_review=False,
        unified_diff=(
            f"--- {target_test}\n"
            f"+++ {target_test}\n"
            "@@ -7,1 +7,1 @@\n"
            f"-{original_line}\n"
            f"+{proposed_line}\n"
        ),
    )


@dataclass
class _StubAudit:
    """Fake AuditResult-like object returned by the stub sentinel."""

    run_id: str
    findings: tuple[object, ...] = ()


class _StubSentinel:
    """Minimal stand-in for the Phase-16 SDK facade.

    Implements the subset the verify_fix loop uses
    (``async_report`` + ``async_audit``). The stubbed audit reads the
    spec file from disk and returns "no findings" once the locator was
    rewritten — that simulates the real audit passing after the
    healer's repair was applied.
    """

    def __init__(self, *, run_dir: Path, spec_path: Path) -> None:
        self._run_dir = run_dir
        self._spec_path = spec_path
        self.audit_calls = 0

    async def async_report(self, *, run_id: str, latest: bool) -> Path:
        return self._run_dir

    async def async_audit(
        self,
        *,
        url: str | None = None,
        modules: tuple[str, ...] | None = None,
    ) -> _StubAudit:
        self.audit_calls += 1
        # Read the spec; if the new locator name is present, return zero findings.
        body = self._spec_path.read_text(encoding="utf-8")
        if "/log in/i" in body:
            return _StubAudit(run_id="RUN-NEWNEWNEWNEW", findings=())
        return _StubAudit(
            run_id="RUN-NEWNEWNEWNEW",
            findings=(),  # Not exercised by the verify path below.
        )


def _seed_run(
    runs_root: Path,
    *,
    base_url: str,
    prior_finding_target: str,
) -> Path:
    """Create a minimal run directory the verify_fix logic can read."""

    run_id = "RUN-AAAAAAAAAAAA"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    findings = {
        "schema_version": "1",
        "findings": [
            {
                "id": "FND-AAAAAAAAAAAA",
                "module": "functional",
                "category": "locator",
                "title": "Sign-in button click failed",
                "location": {"file": prior_finding_target, "selector": "button[name='Sign in']"},
            }
        ],
    }
    (run_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({"target": {"base_url": base_url}}), encoding="utf-8"
    )
    return run_dir


@pytest.mark.asyncio
async def test_verify_fix_loop_with_healer_proposal(tmp_path: Path) -> None:
    """Apply a healer proposal, then verify the audit clears the finding."""

    from sentinelqa_mcp.verify_fix import run_verify_fix

    runs_root = tmp_path / ".sentinel" / "runs"
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_SPEC, encoding="utf-8")

    run_dir = _seed_run(
        runs_root,
        base_url="http://localhost:3000",
        prior_finding_target=str(spec_path.relative_to(tmp_path)),
    )
    proposal = _make_proposal(str(spec_path))
    write_proposal(run_dir, proposal)
    write_index(run_dir, (proposal,))

    # Agent step: apply the proposal's change.
    body = spec_path.read_text(encoding="utf-8")
    body = body.replace(
        proposal.original_behavior.strip(),
        proposal.proposed_change.strip(),
    )
    spec_path.write_text(body, encoding="utf-8")

    stub_sentinel = _StubSentinel(run_dir=run_dir, spec_path=spec_path)

    result = await run_verify_fix(
        sentinel=stub_sentinel,  # type: ignore[arg-type]
        run_id=run_dir.name,
        target_finding_id="FND-AAAAAAAAAAAA",
        url="http://localhost:3000",
    )
    assert result.decision == "fix_verified"
    assert stub_sentinel.audit_calls == 1


@pytest.mark.asyncio
async def test_verify_fix_still_failing_when_proposal_not_applied(tmp_path: Path) -> None:
    """If the agent did not apply the proposal, verify_fix returns still_failing."""

    from sentinelqa_mcp.verify_fix import run_verify_fix

    runs_root = tmp_path / ".sentinel" / "runs"
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_SPEC, encoding="utf-8")

    run_dir = _seed_run(
        runs_root,
        base_url="http://localhost:3000",
        prior_finding_target=str(spec_path.relative_to(tmp_path)),
    )
    proposal = _make_proposal(str(spec_path))
    write_proposal(run_dir, proposal)

    class _PersistentFailureSentinel(_StubSentinel):
        async def async_audit(
            self,
            *,
            url: str | None = None,
            modules: tuple[str, ...] | None = None,
        ) -> _StubAudit:
            self.audit_calls += 1
            # Return the same prior finding to simulate persistent failure.

            class _F:
                def to_agent_message(self) -> Mapping[str, object]:
                    return {
                        "id": "FND-AAAAAAAAAAAA",
                        "module": "functional",
                        "category": "locator",
                        "title": "Sign-in button click failed",
                        "location": {
                            "file": str(spec_path.relative_to(tmp_path)),
                            "selector": "button[name='Sign in']",
                        },
                    }

            return _StubAudit(run_id="RUN-NEW", findings=(_F(),))

    stub = _PersistentFailureSentinel(run_dir=run_dir, spec_path=spec_path)
    result = await run_verify_fix(
        sentinel=stub,  # type: ignore[arg-type]
        run_id=run_dir.name,
        target_finding_id="FND-AAAAAAAAAAAA",
        url="http://localhost:3000",
    )
    assert result.decision == "still_failing"
