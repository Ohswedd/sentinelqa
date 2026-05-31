# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Go-public checklist health (Phase 35.08).

Asserts the checklist file at `docs/release/go-public-checklist.md`:

  * Is a valid Markdown checklist (every `- [ ]` parses).
  * Every relative file/path it references exists on disk.
  * Documents but does NOT execute the `gh repo edit
    --visibility public` flip (the agent must not flip the repo).
  * The announcement-draft file referenced exists and has the
    placeholders that the owner adapts.

The repo flip itself is owner-only; this test only validates that
the artifacts the owner needs to make the flip are in place.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = REPO_ROOT / "docs" / "release" / "go-public-checklist.md"
ANNOUNCEMENT = REPO_ROOT / "docs" / "release" / "announcement-draft.md"

# All Markdown checkbox lines, regardless of state.
CHECKBOX_RE = re.compile(r"^- \[( |x)\]", flags=re.MULTILINE)
RELATIVE_LINK_RE = re.compile(r"\[[^\]]+\]\((\.\.?/[^)\s]+)\)")
DEFINITE_OFF_BACKTICK_RE = re.compile(r"`([^`]+\.(?:md|svg|png|yml|py|toml|json|sh))`")


def _checklist_text() -> str:
    return CHECKLIST.read_text(encoding="utf-8")


def test_checklist_present() -> None:
    assert CHECKLIST.is_file(), f"missing {CHECKLIST}"


def test_announcement_present() -> None:
    assert ANNOUNCEMENT.is_file(), f"missing {ANNOUNCEMENT}"


def test_checklist_has_at_least_one_unchecked_item() -> None:
    """The checklist ships with every box UNticked — the owner ticks them at flip time."""
    text = _checklist_text()
    matches = CHECKBOX_RE.findall(text)
    assert matches, "checklist must include at least one `- [ ]` item"
    unchecked = sum(1 for m in matches if m == " ")
    assert unchecked > 0, (
        "go-public-checklist.md ships with every box pre-ticked; that "
        "defeats the purpose of an owner pre-flight checklist."
    )


def test_relative_paths_resolve_on_disk() -> None:
    """Every `[..](./path/...)` link in the checklist resolves."""
    text = _checklist_text()
    failures: list[str] = []
    for match in RELATIVE_LINK_RE.finditer(text):
        url = match.group(1).split("#", 1)[0].split("?", 1)[0]
        candidate = (CHECKLIST.parent / url).resolve()
        if not candidate.exists():
            failures.append(f"{match.group(0)} → {candidate} (missing)")
    assert not failures, "broken relative links in checklist:\n" + "\n".join(failures)


def test_documents_but_does_not_execute_the_flip() -> None:
    """The flip commands are documented inside a fenced block, not auto-run."""
    text = _checklist_text()
    assert (
        "gh repo edit Ohswedd/sentinelqa --visibility public" in text
    ), "checklist must document the flip command verbatim."
    # Find which line that command lives on, and ensure it sits inside
    # a fenced code block.
    lines = text.splitlines()
    target = "gh repo edit Ohswedd/sentinelqa --visibility public"
    idx = next(i for i, line in enumerate(lines) if target in line)
    fences_above = sum(1 for line in lines[:idx] if line.startswith("```"))
    assert fences_above % 2 == 1, (
        "The visibility-flip command must live inside a ``` fenced "
        "code block (so it reads as documentation, not as an action "
        "the agent should run)."
    )


def test_checklist_lists_required_artifacts() -> None:
    text = _checklist_text()
    # The checklist must reference each Phase-35 artifact by name so
    # the owner cross-checks they exist before flipping.
    must_mention = (
        "README.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "ISSUE_TEMPLATE",
        "pull_request_template",
        "NOTICE",
        "dependabot.yml",
        "docs-deploy.yml",
        "branch-protection.md",
        "social-preview",
        "Private Vulnerability Reporting",
    )
    missing = [m for m in must_mention if m not in text]
    assert not missing, f"go-public-checklist.md is missing required artifact references: {missing}"


def test_announcement_draft_carries_safety_callout() -> None:
    """Per CLAUDE.md §6, the announcement must keep the safety boundary front-and-center."""
    text = ANNOUNCEMENT.read_text(encoding="utf-8")
    assert "authorized testing only" in text.lower()
    assert "no stealth" in text.lower()
    assert "Safety boundary" in text or "safety boundary" in text.lower()


def test_announcement_draft_includes_release_notes_block() -> None:
    text = ANNOUNCEMENT.read_text(encoding="utf-8")
    assert "v0.7.0" in text
    assert "uv pip install sentinelqa-cli" in text
    assert "docs.sentinelqa.dev" in text


def test_checklist_carries_signoff_block() -> None:
    text = _checklist_text()
    assert "Sign-off" in text
    # Each row of the sign-off block:
    for field in ("Owner", "Date", "Tag at flip"):
        assert field in text, f"sign-off block missing {field!r} row"


def test_checklist_states_flip_is_owner_only() -> None:
    text = _checklist_text().lower()
    assert "owner-only" in text or "owner only" in text or "do not run these as the agent" in text
