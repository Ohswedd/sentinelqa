"""Phase 20.07 — `sentinel fix` CLI integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.models import RepairProposal
from engine.healer.writer import write_index, write_proposal
from typer.testing import CliRunner

_GENERATED_BANNER = """\
// SENTINELQA AUTO-GENERATED SPEC
// generated_at: 2026-05-01T12:00:00+00:00

import { test, expect } from '@playwright/test';

test('signs in', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: /sign in/i }).click();
});
"""


def _seed_run_with_proposals(
    tmp_path: Path,
    *,
    proposals: tuple[RepairProposal, ...],
) -> Path:
    runs_root = tmp_path / ".sentinel" / "runs"
    run_id = "RUN-AAAAAAAAAAAA"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    for proposal in proposals:
        write_proposal(run_dir, proposal)
    write_index(run_dir, proposals)
    return run_dir


def _make_locator_proposal(
    *,
    target: Path,
    target_test_path: str = "tests/sentinel/login.spec.ts",
    confidence: float = 0.95,
) -> RepairProposal:
    gen = IdGenerator()
    original_line = "  await page.getByRole('button', { name: /sign in/i }).click();"
    proposed_line = "  await page.getByRole('button', { name: /log in/i }).click();"
    return RepairProposal(
        id=gen.new("RPR"),
        kind="locator",
        target_test=target_test_path,
        target_test_line=7,
        original_behavior=original_line,
        proposed_change=proposed_line,
        confidence=confidence,
        reason="Sign in renamed to Log in.",
        evidence=(Evidence(id=gen.new("EVD"), type="source_ref", path=target),),
        requires_human_review=False,
        unified_diff=(
            f"--- {target_test_path}\n"
            f"+++ {target_test_path}\n"
            "@@ -7,1 +7,1 @@\n"
            f"-{original_line}\n"
            f"+{proposed_line}\n"
        ),
    )


def _setup_chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_fix_review_only_lists_proposals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    proposal = _make_locator_proposal(target=spec_path)
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix"])
    assert result.exit_code == 0, result.stderr
    assert "Proposal" in result.stdout
    assert proposal.id in result.stdout
    assert "Reason:" in result.stdout


def test_fix_safe_apply_applies_high_confidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    # Force banner mtime BEFORE generated_at so detect_banner_status
    # treats it as healer-managed (not hand-edited).
    import os

    os.utime(spec_path, (1735660800, 1735660800))

    proposal = _make_locator_proposal(target=spec_path, confidence=0.95)
    run_dir = _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix", "--apply", "safe"])
    assert result.exit_code == 0, result.stderr
    assert f"applied {proposal.id}" in result.stdout
    body = spec_path.read_text(encoding="utf-8")
    assert "/log in/i" in body
    # Audit log written.
    audit_lines = (run_dir / "audit.log").read_text(encoding="utf-8").strip().splitlines()
    assert any("healer.apply" in line for line in audit_lines)


def test_fix_dry_run_does_not_modify_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    import os

    os.utime(spec_path, (1735660800, 1735660800))

    proposal = _make_locator_proposal(target=spec_path)
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    before = spec_path.read_text(encoding="utf-8")
    result = runner.invoke(cli, ["fix", "--apply", "safe", "--dry-run"])
    assert result.exit_code == 0, result.stderr
    assert f"would-apply {proposal.id}" in result.stdout
    assert spec_path.read_text(encoding="utf-8") == before


def test_fix_refuses_hand_edited_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    # No banner — hand-owned.
    spec_path.write_text(
        "import { test } from '@playwright/test';\n" "test('a', async () => {});\n",
        encoding="utf-8",
    )
    proposal = _make_locator_proposal(target=spec_path)
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix", "--apply", "safe"])
    assert result.exit_code == 0
    assert f"skip {proposal.id}" in result.stdout
    assert "hand-edited" in result.stdout


def test_fix_json_mode_emits_machine_readable_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    proposal = _make_locator_proposal(target=spec_path)
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["--json", "fix"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["count"] == 1
    assert proposal.id in payload["reviewed"]


def test_fix_no_proposals_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    _seed_run_with_proposals(tmp_path, proposals=())

    result = runner.invoke(cli, ["fix"])
    assert result.exit_code == 0
    assert "No healer proposals" in result.stdout


def test_fix_no_run_dir_returns_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["fix"])
    assert result.exit_code == 2
    combined = (result.stderr or "") + (result.stdout or "")
    assert "no run directory found" in combined


def test_fix_unknown_apply_value_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    _seed_run_with_proposals(tmp_path, proposals=())
    result = runner.invoke(cli, ["fix", "--apply", "wild"])
    assert result.exit_code == 2
    combined = (result.stderr or "") + (result.stdout or "")
    assert "unknown --apply" in combined


def test_fix_review_only_overrides_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    import os

    os.utime(spec_path, (1735660800, 1735660800))
    proposal = _make_locator_proposal(target=spec_path)
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    before = spec_path.read_text(encoding="utf-8")
    result = runner.invoke(cli, ["fix", "--apply", "safe", "--review-only"])
    assert result.exit_code == 0
    assert spec_path.read_text(encoding="utf-8") == before
    assert "Proposal" in result.stdout


def test_fix_apply_with_missing_target_file_is_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    """When the target spec file is missing, banner detects hand-edited and the apply is skipped."""

    _setup_chdir(tmp_path, monkeypatch)
    proposal = _make_locator_proposal(
        target=tmp_path / "missing.spec.ts",
        target_test_path="tests/sentinel/login.spec.ts",
    )
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix", "--apply", "safe"])
    assert result.exit_code == 0
    assert f"skip {proposal.id}" in result.stdout


def test_fix_specific_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    proposal = _make_locator_proposal(target=spec_path)
    run_dir = _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix", "--run", run_dir.name])
    assert result.exit_code == 0
    assert proposal.id in result.stdout


def test_fix_unknown_run_id_returns_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    (tmp_path / ".sentinel" / "runs").mkdir(parents=True)
    result = runner.invoke(cli, ["fix", "--run", "RUN-DOESNOTEXIST"])
    assert result.exit_code == 2


def test_fix_dry_run_with_diff_that_fails_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli: typer.Typer,
) -> None:
    _setup_chdir(tmp_path, monkeypatch)
    spec_path = tmp_path / "tests" / "sentinel" / "login.spec.ts"
    spec_path.parent.mkdir(parents=True)
    # Spec is generated-banner-compatible but the proposal's original line
    # doesn't appear inside — the apply will fail cleanly.
    spec_path.write_text(_GENERATED_BANNER, encoding="utf-8")
    import os

    os.utime(spec_path, (1735660800, 1735660800))

    proposal_disjoint = _make_locator_proposal(target=spec_path)
    # Mutate the proposal to point at a non-existent original line.
    proposal = proposal_disjoint.model_copy(
        update={"original_behavior": "// this line is not in the spec"}
    )
    _seed_run_with_proposals(tmp_path, proposals=(proposal,))

    result = runner.invoke(cli, ["fix", "--apply", "safe"])
    # The apply failure surfaces as exit code 6 (test execution failed).
    assert result.exit_code == 6
