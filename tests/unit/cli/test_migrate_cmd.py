# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for ``sentinel migrate``."""

from __future__ import annotations

from pathlib import Path

from sentinel_cli.commands.migrate_cmd import (
    MigrationCandidate,
    discover_candidates,
    render_adapter_spec,
)


def _write(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "test('x', () => {});\n", encoding="utf-8")
    return path


def test_discover_finds_cypress_e2e_files(tmp_path: Path) -> None:
    _write(tmp_path / "cypress" / "e2e" / "login.cy.ts")
    _write(tmp_path / "cypress" / "e2e" / "checkout.cy.js")
    found = discover_candidates(tmp_path)
    sources = {c.source.name for c in found}
    assert sources == {"login.cy.ts", "checkout.cy.js"}
    assert all(c.framework == "cypress" for c in found)


def test_discover_finds_playwright_specs(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")
    _write(tmp_path / "e2e" / "login.spec.js")
    found = discover_candidates(tmp_path)
    sources = {c.source.name for c in found}
    assert sources == {"smoke.spec.ts", "login.spec.js"}
    assert all(c.framework == "playwright" for c in found)


def test_discover_skips_already_migrated_tree(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")
    _write(tmp_path / "tests" / "sentinel" / "migrated" / "smoke.spec.ts")
    found = discover_candidates(tmp_path)
    assert len(found) == 1
    assert "migrated" not in found[0].source.as_posix()


def test_framework_override_filters_results(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")  # Playwright
    _write(tmp_path / "cypress" / "e2e" / "login.cy.ts")  # Cypress
    only_cypress = discover_candidates(tmp_path, framework_override="cypress")
    assert {c.source.name for c in only_cypress} == {"login.cy.ts"}
    only_playwright = discover_candidates(tmp_path, framework_override="playwright")
    assert {c.source.name for c in only_playwright} == {"smoke.spec.ts"}


def test_flow_tag_heuristics() -> None:
    """The flow tag must come from the file or parent directory name."""

    cases = [
        ("cypress/e2e/login.cy.ts", "login"),
        ("cypress/e2e/signup.cy.ts", "signup"),
        ("cypress/e2e/checkout.cy.ts", "checkout"),
        ("tests/admin/users.spec.ts", "admin"),
        ("tests/profile.spec.ts", "profile"),
    ]
    for path_str, expected_tag in cases:
        c = MigrationCandidate(
            framework="cypress",
            source=Path(path_str),
            flow_tag="",  # overwritten by discover_candidates, but unused here
            priority_tag="p1",
        )
        # Re-run the heuristic via discover_candidates' helper.
        from sentinel_cli.commands.migrate_cmd import _infer_flow_tag

        assert _infer_flow_tag(c.source) == expected_tag


def test_render_adapter_spec_emits_required_tags(tmp_path: Path) -> None:
    candidate = MigrationCandidate(
        framework="playwright",
        source=tmp_path / "tests" / "checkout.spec.ts",
        flow_tag="checkout",
        priority_tag="p1",
    )
    body = render_adapter_spec(candidate=candidate, source_root=tmp_path)
    # The generated banner is non-negotiable — the healer / generator
    # contract relies on it.
    assert "SENTINELQA AUTO-GENERATED" in body
    # Tags the planner consumes.
    for tag in ("@p1", "@module:functional", "@flow:checkout"):
        assert tag in body
    # Source pointer for the reviewer.
    assert "tests/checkout.spec.ts" in body


def test_cypress_adapter_marks_via_cypress(tmp_path: Path) -> None:
    candidate = MigrationCandidate(
        framework="cypress",
        source=tmp_path / "cypress" / "e2e" / "login.cy.ts",
        flow_tag="login",
        priority_tag="p1",
    )
    body = render_adapter_spec(candidate=candidate, source_root=tmp_path)
    assert "via:cypress" in body
    assert "@flow:login" in body
