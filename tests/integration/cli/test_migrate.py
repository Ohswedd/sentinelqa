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
