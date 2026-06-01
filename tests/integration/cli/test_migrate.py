# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""End-to-end CLI tests for ``sentinel migrate``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sentinel_cli.app import build_app


def _write(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "test('x', () => {});\n", encoding="utf-8")
    return path


def test_migrate_writes_adapter_specs(tmp_path: Path) -> None:
    """A repo with two source tests must produce two adapter specs."""

    _write(tmp_path / "cypress" / "e2e" / "login.cy.ts")
    _write(tmp_path / "tests" / "checkout.spec.ts")

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output

    migrated_root = tmp_path / "tests" / "sentinel" / "migrated"
    assert migrated_root.is_dir()
    files = sorted(p.name for p in migrated_root.iterdir())
    # File names are slugged from the source path.
    assert "cypress-e2e-login-cy.spec.ts" in files
    assert "tests-checkout-spec.spec.ts" in files

    # Manifest exists and lists both results.
    manifest = json.loads(
        (tmp_path / ".sentinel" / "migrate" / "manifest.json").read_text(encoding="utf-8")
    )
    sources = {r["source"] for r in manifest["results"]}
    assert any("login.cy.ts" in s for s in sources)
    assert any("checkout.spec.ts" in s for s in sources)


def test_migrate_dry_run_writes_nothing(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["migrate", "--path", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "(dry-run; no files written)" in result.output
    assert not (tmp_path / "tests" / "sentinel" / "migrated").exists()
    assert not (tmp_path / ".sentinel" / "migrate" / "manifest.json").exists()


def test_migrate_with_no_sources_prints_helpful_message(tmp_path: Path) -> None:
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No Cypress or Playwright tests found" in result.output


def test_migrate_json_mode_emits_structured_results(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")

    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--json", "migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["command"] == "migrate"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["framework"] == "playwright"
    # The slug heuristic produces "smoke-spec" for "smoke.spec.ts" because
    # "smoke" is not in the curated flow list.
    assert payload["results"][0]["flow_tag"] == "smoke-spec"


def test_migrate_help_lists_migrate_command() -> None:
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--help"], terminal_width=120)
    assert result.exit_code == 0
    assert "migrate" in result.output


def test_migrate_invalid_framework_exits_with_error(tmp_path: Path) -> None:
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["migrate", "--path", str(tmp_path), "--framework", "selenium"])
    assert result.exit_code == 2
    assert "must be 'cypress' or 'playwright'" in result.output


def test_migrate_no_sources_json_mode(tmp_path: Path) -> None:
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--json", "migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["command"] == "migrate"
    assert payload["results"] == []


def test_migrate_quiet_mode_writes_files_without_stdout(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--quiet", "migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""
    assert (tmp_path / "tests" / "sentinel" / "migrated").is_dir()


def test_migrate_re_run_marks_unchanged(tmp_path: Path) -> None:
    """Running twice produces 'unchanged' the second time."""

    _write(tmp_path / "tests" / "smoke.spec.ts")
    runner = CliRunner()
    app = build_app()
    runner.invoke(app, ["migrate", "--path", str(tmp_path)])
    second = runner.invoke(app, ["--json", "migrate", "--path", str(tmp_path)])
    assert second.exit_code == 0, second.output
    payload = json.loads(second.stdout)
    statuses = {r["status"] for r in payload["results"]}
    assert statuses == {"unchanged"}


def test_migrate_skipped_when_existing_drifted_without_force(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")
    target = tmp_path / "tests" / "sentinel" / "migrated" / "tests-smoke-spec.spec.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// stale, unrelated content\n", encoding="utf-8")
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--json", "migrate", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    statuses = {r["status"] for r in payload["results"]}
    assert statuses == {"skipped"}


def test_migrate_force_overwrites_existing(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "smoke.spec.ts")
    target = tmp_path / "tests" / "sentinel" / "migrated" / "tests-smoke-spec.spec.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// stale\n", encoding="utf-8")
    runner = CliRunner()
    app = build_app()
    result = runner.invoke(app, ["--json", "migrate", "--path", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    assert "SENTINELQA AUTO-GENERATED" in target.read_text(encoding="utf-8")
