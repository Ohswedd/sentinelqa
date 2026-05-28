"""Integration test: Python wrapper drives the real `sentinel-ts` CLI.

Skipped when the bundled CLI binary at
``packages/ts-runtime/dist/cli.js`` is missing (CI does not build the
TS dist by default for every Python test run — `make test-ts` /
`pnpm build` does). Guards the cross-runtime contract live.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from engine.generator.locator_strategy import audit_specs


def _cli_path() -> Path:
    return Path(__file__).resolve().parents[3] / "packages" / "ts-runtime" / "dist" / "cli.js"


pytestmark = pytest.mark.skipif(
    not _cli_path().exists() or shutil.which("node") is None,
    reason="ts-runtime dist not built or node not available",
)


def _exec() -> str:
    node = shutil.which("node") or "node"
    return f"NODE::{node}::{_cli_path()}"


def test_audit_clean_spec(tmp_path: Path) -> None:
    spec = tmp_path / "clean.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "test('x', async ({ page }) => {\n"
        "  await page.getByRole('button', { name: /go/i }).click();\n"
        "});\n",
        encoding="utf-8",
    )
    result = audit_specs([spec], cwd=tmp_path, executable=_exec())
    assert result.is_clean
    assert result.files_scanned == 1


def test_audit_flags_brittle_spec(tmp_path: Path) -> None:
    spec = tmp_path / "brittle.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "test('x', async ({ page }) => {\n"
        "  await page.locator('div:nth-of-type(3)').click();\n"
        "});\n",
        encoding="utf-8",
    )
    result = audit_specs([spec], cwd=tmp_path, executable=_exec())
    assert not result.is_clean
    assert any("nth" in w.message for w in result.warnings)
