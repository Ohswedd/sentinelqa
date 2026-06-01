"""Banner / hand-edit detection tests."""

from __future__ import annotations

import os
from pathlib import Path

from engine.healer.banner import detect_banner_status

_GENERATED_BANNER = """\
// SENTINELQA AUTO-GENERATED SPEC
// generated_at: 2026-05-01T12:00:00+00:00
// Phase 07 generator + Phase 04 helpers

import { test, expect } from '@playwright/test';

test('signs in', async ({ page }) => {});
"""

_HAND_EDITED = """\
// crafted by hand by an experienced QA engineer
import { test, expect } from '@playwright/test';

test('signs in', async ({ page }) => {});
"""


def test_missing_file_is_hand_owned(tmp_path: Path) -> None:
    status = detect_banner_status(tmp_path / "missing.spec.ts")
    assert status.hand_edited is True
    assert "does not exist" in status.reason


def test_banner_present_unmodified_is_managed(tmp_path: Path) -> None:
    path = tmp_path / "managed.spec.ts"
    path.write_text(_GENERATED_BANNER, encoding="utf-8")
    # Force mtime equal to (or before) the banner's generated_at.
    os.utime(path, (1735660800, 1735660800))  # 2025-01-01
    status = detect_banner_status(path)
    assert status.has_banner is True
    assert status.hand_edited is False


def test_banner_absent_is_hand_owned(tmp_path: Path) -> None:
    path = tmp_path / "owned.spec.ts"
    path.write_text(_HAND_EDITED, encoding="utf-8")
    status = detect_banner_status(path)
    assert status.has_banner is False
    assert status.hand_edited is True
    assert "AUTO-GENERATED" in status.reason


def test_banner_present_but_modified_after_generated_at(tmp_path: Path) -> None:
    path = tmp_path / "drifted.spec.ts"
    path.write_text(_GENERATED_BANNER, encoding="utf-8")
    # Force mtime to 2030 — well after the banner's 2026 generated_at.
    os.utime(path, (1893456000, 1893456000))
    status = detect_banner_status(path)
    assert status.has_banner is True
    assert status.hand_edited is True
    assert "hand-edited" in status.reason


def test_banner_with_malformed_generated_at_still_managed(tmp_path: Path) -> None:
    body = "// SENTINELQA AUTO-GENERATED SPEC\n// generated_at: not-a-date\nconst x = 1;\n"
    path = tmp_path / "managed.spec.ts"
    path.write_text(body, encoding="utf-8")
    status = detect_banner_status(path)
    # No reliable generated_at — we still treat as managed if the banner
    # is present and we have no contradicting signal.
    assert status.has_banner is True
    assert status.hand_edited is False
