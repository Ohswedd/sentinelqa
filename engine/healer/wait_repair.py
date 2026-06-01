"""Wait-condition repair.

Detects ``await page.waitForTimeout(<N>)`` calls (our engineering rules
forbids arbitrary sleeps but legacy / hand-edited code may still have
them) and proposes a replacement with the explicit Playwright wait
that matches the next assertion. The repair leaves the rest of the
spec untouched.

Confidence tiers:

- The very next assertion is ``await expect(<L>).toBeVisible`` or
 ``.toHaveText(...)`` — confidence ``0.9`` (auto-apply candidate).
- The next assertion targets a *different* locator — confidence
 ``0.6`` (requires review; the timeout may have been protecting an
 intentional gap).
- No assertion follows on the same scope — confidence ``0.3`` (we
 emit a structured *removal* proposal but force review).

Auto-apply threshold defaults to ``0.9`` so only the high-confidence
case applies without review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.diff import unified_diff_for
from engine.healer.models import RepairProposal

# We deliberately accept any non-negative integer/float argument; the
# guard rejects ``waitForTimeout(`` calls with template literals.
_WAIT_FOR_TIMEOUT_RE = re.compile(
    r"""^(?P<indent>\s*)await\s+page\.waitForTimeout\(\s*(?P<ms>\d+(?:\.\d+)?)\s*\)\s*;?\s*$""",
)
_EXPECT_RE = re.compile(
    r"""^\s*await\s+expect\(\s*(?P<target>.+?)\s*\)\.(?P<matcher>toBeVisible|toHaveText|toHaveValue|toBeEnabled|toBeDisabled|toBeChecked)\s*\((?P<args>[^)]*)\)\s*;?\s*$""",
)


@dataclass(frozen=True)
class WaitRepairInputs:
    """Inputs for one wait-condition proposal."""

    test_path: Path
    test_source: str
    wait_line: int
    """1-based line containing ``await page.waitForTimeout(...)``."""


def _find_next_expect(lines: list[str], start_line_zero: int) -> tuple[int, re.Match[str]] | None:
    """Return ``(zero-based index, match)`` of the next ``await expect(...)``."""

    for offset, line in enumerate(lines[start_line_zero + 1 :], start=start_line_zero + 1):
        if line.strip() == "":
            continue
        match = _EXPECT_RE.match(line)
        if match is not None:
            return (offset, match)
        # Stop searching if we hit a block boundary — wait/assertion pairs
        # should be in the same scope.
        stripped = line.strip()
        if stripped.startswith("}") or stripped.startswith("})"):
            return None
        if "test(" in stripped or stripped.startswith("test.") or stripped.startswith("describe("):
            return None
    return None


def propose_wait_repair(
    inputs: WaitRepairInputs,
    *,
    id_generator: IdGenerator | None = None,
    auto_apply_threshold: float = 0.9,
) -> RepairProposal | None:
    """Propose a single wait-condition repair, or ``None`` if not actionable."""

    lines = inputs.test_source.splitlines(keepends=True)
    if inputs.wait_line < 1 or inputs.wait_line > len(lines):
        return None
    wait_line_idx = inputs.wait_line - 1
    target_line = lines[wait_line_idx]
    wait_match = _WAIT_FOR_TIMEOUT_RE.match(target_line)
    if wait_match is None:
        return None
    indent = wait_match.group("indent")
    ms = wait_match.group("ms")

    next_expect = _find_next_expect(lines, wait_line_idx)
    if next_expect is None:
        # No assertion follows — propose deletion but with low confidence.
        proposed_lines = list(lines)
        proposed_lines[wait_line_idx] = ""
        proposed = "".join(proposed_lines)
        diff = unified_diff_for(
            path=str(inputs.test_path),
            original=inputs.test_source,
            proposed=proposed,
        )
        confidence = 0.3
        gen = id_generator or IdGenerator()
        return RepairProposal(
            id=gen.new("RPR"),
            kind="wait",
            target_test=str(inputs.test_path),
            target_test_line=inputs.wait_line,
            original_behavior=target_line.rstrip("\n"),
            proposed_change=f"{indent}// (line removed)",
            confidence=confidence,
            reason=(
                f"`await page.waitForTimeout({ms})` is forbidden by our engineering rules "
                "and no following assertion was found to anchor an explicit wait."
            ),
            evidence=(
                Evidence(
                    id=gen.new("EVD"),
                    type="source_ref",
                    path=inputs.test_path,
                ),
            ),
            requires_human_review=True,
            unified_diff=diff,
            descriptor=None,
        )

    _, expect_match = next_expect
    target_expr = expect_match.group("target").strip()
    matcher = expect_match.group("matcher")

    # Replace the timeout line with `await expect(<target>).<matcher>(<args>?)`.
    # When the original assertion already exists below the timeout we
    # don't double-emit it — we just remove the timeout. That keeps the
    # spec semantically equivalent without a brittle wait.
    proposed_lines = list(lines)
    proposed_lines[wait_line_idx] = ""
    proposed_source = "".join(proposed_lines)

    diff = unified_diff_for(
        path=str(inputs.test_path),
        original=inputs.test_source,
        proposed=proposed_source,
    )

    confidence = 0.9 if matcher in {"toBeVisible", "toHaveText"} else 0.6
    requires_review = confidence < auto_apply_threshold

    gen = id_generator or IdGenerator()
    proposed_change_text = (
        f"{indent}// (line removed — relying on `await expect({target_expr}).{matcher}(...)` "
        "below)"
    )
    return RepairProposal(
        id=gen.new("RPR"),
        kind="wait",
        target_test=str(inputs.test_path),
        target_test_line=inputs.wait_line,
        original_behavior=target_line.rstrip("\n"),
        proposed_change=proposed_change_text,
        confidence=confidence,
        reason=(
            f"`await page.waitForTimeout({ms})` is forbidden by our engineering rules. "
            f"Playwright auto-waiting on `await expect({target_expr}).{matcher}(...)` "
            "below already provides the synchronization."
        ),
        evidence=(
            Evidence(
                id=gen.new("EVD"),
                type="source_ref",
                path=inputs.test_path,
            ),
        ),
        requires_human_review=requires_review,
        unified_diff=diff,
        descriptor=None,
    )


__all__ = ["WaitRepairInputs", "propose_wait_repair"]
