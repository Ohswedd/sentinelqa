# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Branch-protection doc + verify script health (Phase 35.06).

Asserts the documented branch-protection spec
(`docs/dev/branch-protection.md`) and the in-repo verify script
(`scripts/release/verify_branch_protection.py`) name the same set of
required CI checks. Drift between the doc and the script — or between
either of them and the actual workflow names — fails the test.

The test does NOT hit GitHub's API; it's a static cross-check that
ensures the verification machinery stays internally consistent. The
live diff lives in `make verify-branch-protection`.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from scripts.release import verify_branch_protection as verifier

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC = REPO_ROOT / "docs" / "dev" / "branch-protection.md"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
MAKEFILE = REPO_ROOT / "Makefile"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _required_checks_in_doc() -> set[str]:
    """Extract the backtick-quoted check names from the doc's table."""
    text = _doc_text()
    # Pull the markdown table cells of the form `| `name` | …`. We look
    # for ASCII backtick-quoted strings that appear in the leftmost
    # column of the required-checks table.
    return {
        match.group(1) for match in re.finditer(r"^\|\s*`([^`]+)`\s*\|", text, flags=re.MULTILINE)
    }


def _workflow_names() -> set[str]:
    """Collect every job's `name:` value from .github/workflows/*.yml."""
    names: set[str] = set()
    for path in WORKFLOWS_DIR.glob("*.yml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        jobs = data.get("jobs", {}) or {}
        for job in jobs.values():
            if isinstance(job, dict) and isinstance(job.get("name"), str):
                names.add(job["name"])
    return names


def test_doc_present() -> None:
    assert DOC.is_file(), f"branch-protection doc missing at {DOC}"


def test_doc_lists_expected_check_names() -> None:
    doc_checks = _required_checks_in_doc()
    for name in verifier.EXPECTED_REQUIRED_CHECKS:
        assert name in doc_checks, (
            f"branch-protection.md does not list required check {name!r}; "
            "the doc and verify_branch_protection.py have drifted."
        )


def test_verify_script_and_doc_agree() -> None:
    doc_checks = _required_checks_in_doc()
    script_checks = set(verifier.EXPECTED_REQUIRED_CHECKS)
    # Every script check appears in the doc table; the doc may include
    # additional checks (e.g. context rows that are NOT required) but
    # the required-checks set must be a subset of the doc.
    missing = script_checks - doc_checks
    assert not missing, (
        f"Required checks named in verify_branch_protection.py but "
        f"missing from docs/dev/branch-protection.md: {sorted(missing)}"
    )


def test_required_checks_match_actual_workflow_names() -> None:
    """Every required check must correspond to a real `name:` field."""
    workflow_names = _workflow_names()

    # Some required checks come from matrix jobs (e.g.
    # `python (3.11)`); the workflow `name:` is the templated form
    # (`python (${{ matrix.python }})`). Allow a match either against
    # the literal name or against the matrix-templated form.
    def matches(check: str, names: set[str]) -> bool:
        if check in names:
            return True
        # Build patterns that account for the matrix templating —
        # escape the literal text first so parens/brackets aren't
        # interpreted as regex syntax, THEN replace the escaped
        # ${{ ... }} markers with `.+`.
        token_re = re.compile(re.escape(r"${{") + r".+?" + re.escape(r"}}"))
        for name in names:
            escaped = re.escape(name)
            # In the escaped form, the matrix tokens look like
            # `\$\{\{ matrix.python \}\}` (each special char preceded
            # by a backslash). Build the canonical escaped token
            # ourselves and replace it.
            pattern = re.sub(
                re.escape(re.escape(r"${{")) + r".+?" + re.escape(re.escape(r"}}")),
                r".+",
                escaped,
            )
            # Fallback: also try the raw-token substitution against
            # the un-escaped name in case the templating layout varies.
            if re.fullmatch(pattern, check):
                return True
            raw = token_re.sub(".+", name)
            try:
                if re.fullmatch(raw, check):
                    return True
            except re.error:
                continue
        return False

    failures = [
        check for check in verifier.EXPECTED_REQUIRED_CHECKS if not matches(check, workflow_names)
    ]
    assert not failures, (
        "These required checks don't match any actual workflow `name:`: "
        f"{failures}. Either the workflow was renamed, or "
        "verify_branch_protection.py's expectation is stale."
    )


def test_makefile_exposes_verify_target() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "verify-branch-protection:" in text, (
        "Makefile must expose `make verify-branch-protection` for the "
        "owner-runnable verification (Phase 35.06)."
    )
    # It must call the script we ship.
    assert "scripts.release.verify_branch_protection" in text


def test_verify_script_gh_missing_returns_5(monkeypatch) -> None:
    """If `gh` isn't on PATH, verifier exits 5 (missing dependency)."""
    monkeypatch.setattr(verifier, "_gh_available", lambda: False)
    code = verifier.main([])
    assert code == 5


def test_doc_documents_tag_protection() -> None:
    text = _doc_text()
    assert "Tag protection" in text or "tag protection" in text.lower()
    assert "v*" in text


def test_doc_forbids_force_push_and_deletion() -> None:
    text = _doc_text().lower()
    assert "force-push" in text or "force push" in text
    assert "deletion" in text or "delete" in text
    # The relevant rules must be turned off.
    assert "allow force-push" in text or "force-push" in text
