# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""LLM-generated remediation patches (v1.4.0).

The Healer's existing :class:`RepairProposal` carries a
``unified_diff`` field; this module populates it via an LLM and
guards the output against the canonical "do not weaken the test"
rules:

* No removed ``expect`` / ``assert`` calls.
* No removed ``await page.waitFor*`` calls.
* No change to the test's ``test.describe`` or ``test('...')``
  identifier (renaming a test silences it).
* No removed test files.
* No more than one file changed per proposal.
* No diff hunks larger than 60 lines.

The patch builder is pure — tests inject a stub LLM that emits a
canned diff and assert on the verdict + safety violations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class PatchProposalRequest:
    """Inputs to the patch builder."""

    failing_test_id: str
    failing_test_path: str
    failure_summary: str
    relevant_source_excerpt: str  # the implementation file the test exercises
    source_path: str
    expectation: str = ""  # one sentence: "what the test wants"
    max_diff_lines: int = 60


@dataclass(frozen=True, slots=True)
class PatchVerdict:
    """The output of the safety-checked builder."""

    proposed: bool
    unified_diff: str
    rationale: str
    safety_violations: tuple[str, ...] = field(default_factory=tuple)
    requires_human_review: bool = True


_SYSTEM_PROMPT: Final[str] = (
    "You are an expert software engineer producing a minimal "
    "unified-diff patch that makes a failing test pass without "
    "weakening it. You MUST follow ALL of these rules:\n"
    "- Touch at most ONE source file (never the test file).\n"
    "- Do not delete, rename, or weaken any expect / assert call.\n"
    "- Do not add a try/except that swallows the failure.\n"
    "- Do not silence the test via `test.skip` / `.only`.\n"
    "- Keep the diff under 60 lines.\n"
    "- Output ONLY the unified-diff text inside a ```diff fenced "
    "block. No prose, no apology, no explanation.\n"
    "If you cannot satisfy these rules, output the literal string "
    "NO_SAFE_PATCH between the fences and nothing else."
)


_NO_PATCH_MARKER = "NO_SAFE_PATCH"

# Regex used to detect violations on a generated diff.
_REMOVED_EXPECT_RE = re.compile(r"^-\s*expect\s*\(", re.MULTILINE)
_REMOVED_ASSERT_RE = re.compile(r"^-\s*assert\s+", re.MULTILINE)
_REMOVED_WAIT_RE = re.compile(r"^-\s*(?:await\s+)?page\.waitFor", re.MULTILINE)
_RENAMED_TEST_RE = re.compile(r"^-\s*test\s*\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
_TEST_SKIP_RE = re.compile(r"^\+.*test\.(?:skip|only)\b", re.MULTILINE)
_TRY_EXCEPT_RE = re.compile(r"^\+\s*(?:try\s*\{|try:)", re.MULTILINE)
_DIFF_HEADER_RE = re.compile(r"^(?:diff --git|---|\+\+\+)\s+", re.MULTILINE)
_FILE_RE = re.compile(r"^\+\+\+\s+(?:b/)?(\S+)", re.MULTILINE)
_FENCED_DIFF_RE = re.compile(r"```(?:diff)?\s*(.*?)```", re.DOTALL)


def _strip_fences(raw: str) -> str:
    """Return the inner diff text from a fenced ```diff block.

    Falls back to the raw input when no fence is present.
    """

    match = _FENCED_DIFF_RE.search(raw)
    if match is None:
        return raw.strip()
    return match.group(1).strip()


def _count_diff_lines(diff: str) -> int:
    """Number of ``+`` / ``-`` lines (ignoring headers + context)."""

    count = 0
    for line in diff.splitlines():
        if not line:
            continue
        if line.startswith(("+++", "---", "@@", "diff --git")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def _files_touched(diff: str) -> tuple[str, ...]:
    """Extract the set of files touched by the diff."""

    return tuple(sorted(set(_FILE_RE.findall(diff))))


def safety_check(diff: str, request: PatchProposalRequest) -> tuple[str, ...]:
    """Return the list of safety violations (empty when clean)."""

    if not diff.strip():
        return ("Empty diff",)

    violations: list[str] = []
    if _REMOVED_EXPECT_RE.search(diff):
        violations.append("Removed `expect(...)` call")
    if _REMOVED_ASSERT_RE.search(diff):
        violations.append("Removed `assert ...` call")
    if _REMOVED_WAIT_RE.search(diff):
        violations.append("Removed a `page.waitFor*` call")
    if _RENAMED_TEST_RE.search(diff):
        violations.append("Removed a `test('...')` declaration")
    if _TEST_SKIP_RE.search(diff):
        violations.append("Added `test.skip` / `.only`")
    if _TRY_EXCEPT_RE.search(diff):
        violations.append("Wrapped failing code in try/except — likely swallows the bug")

    files = _files_touched(diff)
    if len(files) > 1:
        violations.append(f"Diff touches {len(files)} files; only 1 allowed")
    if any(f == request.failing_test_path for f in files):
        violations.append("Diff touches the test file itself — fixes go in implementation")

    if _count_diff_lines(diff) > request.max_diff_lines:
        violations.append(f"Diff has more than {request.max_diff_lines} +/- lines")

    return tuple(violations)


def build_user_prompt(request: PatchProposalRequest) -> str:
    """Compose the locked user message handed to the LLM."""

    excerpt = request.relevant_source_excerpt
    if len(excerpt) > 4000:
        excerpt = excerpt[:4000] + "\n...(truncated)\n"
    return (
        "Failing test:\n"
        f"  id   = {request.failing_test_id}\n"
        f"  file = {request.failing_test_path}\n\n"
        "Failure summary (deterministic side):\n"
        f"{request.failure_summary}\n\n"
        "What the test expects:\n"
        f"{request.expectation or '(not provided)'}\n\n"
        "Implementation source under audit:\n"
        f"  file = {request.source_path}\n"
        "```\n"
        f"{excerpt}\n"
        "```"
    )


def build_patch(
    request: PatchProposalRequest,
    *,
    adapter: object | None = None,
    model: str = "claude-3-5-sonnet-latest",
) -> PatchVerdict:
    """Ask the LLM for a unified diff and validate the response."""

    if adapter is None:
        return PatchVerdict(
            proposed=False,
            unified_diff="",
            rationale="No LLM adapter wired.",
            safety_violations=("no-adapter",),
        )

    user_prompt = build_user_prompt(request)
    try:
        raw, available, detail = adapter(  # type: ignore[operator]
            _SYSTEM_PROMPT, user_prompt, model
        )
    except Exception as exc:
        return PatchVerdict(
            proposed=False,
            unified_diff="",
            rationale=f"Adapter raised: {type(exc).__name__}: {exc}",
            safety_violations=("adapter-exception",),
        )

    if not available or not raw.strip():
        return PatchVerdict(
            proposed=False,
            unified_diff="",
            rationale=detail or "Adapter returned empty response.",
            safety_violations=("provider-unavailable",),
        )

    body = _strip_fences(raw)
    if body.strip() == _NO_PATCH_MARKER:
        return PatchVerdict(
            proposed=False,
            unified_diff="",
            rationale="LLM declined: no safe patch available.",
            safety_violations=(),
        )

    if _DIFF_HEADER_RE.search(body) is None:
        return PatchVerdict(
            proposed=False,
            unified_diff="",
            rationale="Response did not contain a unified-diff header.",
            safety_violations=("invalid-diff-format",),
        )

    violations = safety_check(body, request)
    if violations:
        return PatchVerdict(
            proposed=False,
            unified_diff=body,
            rationale="Safety check rejected the LLM-proposed patch.",
            safety_violations=violations,
            requires_human_review=True,
        )

    return PatchVerdict(
        proposed=True,
        unified_diff=body,
        rationale="Safety-checked LLM patch.",
        safety_violations=(),
        requires_human_review=True,
    )


__all__ = [
    "PatchProposalRequest",
    "PatchVerdict",
    "build_patch",
    "build_user_prompt",
    "safety_check",
]
