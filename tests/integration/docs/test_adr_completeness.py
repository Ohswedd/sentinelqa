"""ADR completeness guard.

CLAUDE.md §34 enumerates the architectural decisions that **must** have an
Accepted ADR. This test asserts that each trigger maps to at least one
ADR file under ``docs/adr/`` whose ``## Status`` line is ``Accepted``.

When a CLAUDE §34 trigger is reached without an ADR landing in the same
phase, the phase is incomplete (CLAUDE.md §44). This test is the
mechanical guard for that contract.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = REPO_ROOT / "docs" / "adr"

# Map each CLAUDE §34 trigger to one or more ADR filenames that cover it.
# Adding a trigger here without adding the ADR will fail the test.
TRIGGER_COVERAGE: dict[str, tuple[str, ...]] = {
    "Runtime architecture": (
        "0001-repository-structure.md",
        "0002-language-strategy.md",
        "0009-python-ts-protocol.md",
    ),
    "Plugin system": ("0029-plugin-architecture.md",),
    "Config schema": ("0005-config-schema.md",),
    "Scoring algorithm": ("0019-quality-scoring.md",),
    "Report schema": ("0008-report-schemas-and-reporter.md",),
    "Security policy": (
        "0006-safety-policy.md",
        "0018-security-module.md",
    ),
    "Agent / MCP design": ("0023-mcp-agent-interface.md",),
    "Cloud boundary": (
        "0033-cloud-boundary.md",
        "0036-cloud-delayed-until-cli-traction.md",
    ),
}

STATUS_RE = re.compile(r"^## Status\s*\n+([^\n#]+)", re.MULTILINE)


def _accepted_adrs() -> set[str]:
    accepted: set[str] = set()
    for adr in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"):
        text = adr.read_text(encoding="utf-8")
        match = STATUS_RE.search(text)
        if not match:
            continue
        status_line = match.group(1).strip()
        # The template uses `Proposed | Accepted | Superseded by ... | Deprecated`
        # as the literal selector — skip un-touched template files.
        if "|" in status_line:
            continue
        if status_line.startswith("Accepted") or status_line == "Accepted":
            accepted.add(adr.name)
    return accepted


def test_every_claude_section_34_trigger_has_an_accepted_adr() -> None:
    accepted = _accepted_adrs()
    missing: list[str] = []
    for trigger, candidates in TRIGGER_COVERAGE.items():
        if not any(name in accepted for name in candidates):
            missing.append(f"{trigger}: expected one of {candidates}, none Accepted")
    assert not missing, "ADR completeness gaps:\n" + "\n".join(f"  - {m}" for m in missing)


def test_prd_section_31_open_questions_all_have_adrs() -> None:
    expected = (
        "0034-python-cli-typescript-runtime.md",
        "0035-generated-tests-in-user-repo.md",
        "0036-cloud-delayed-until-cli-traction.md",
        "0037-llm-provider-agnostic.md",
        "0038-mcp-day-one.md",
        "0039-planner-deterministic-llm-split.md",
        "0040-visual-built-in-first.md",
        "0041-framework-agnostic-with-nextjs.md",
    )
    accepted = _accepted_adrs()
    missing = [name for name in expected if name not in accepted]
    assert not missing, "Missing Accepted ADRs for PRD §31 open questions:\n" + "\n".join(
        f"  - {m}" for m in missing
    )
