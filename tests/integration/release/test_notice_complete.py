# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""NOTICE completeness (Phase 35.03).

Every file under `packages/shared-schema/external/` must have a
matching attribution entry in `NOTICE`. The Phase 35.03 audit script
also pins the inventory in `VENDORED_EXTERNALS` — this test makes the
contract explicit and independent of the audit's internal state.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTICE = REPO_ROOT / "NOTICE"
EXTERNAL_DIR = REPO_ROOT / "packages" / "shared-schema" / "external"


def _notice_text() -> str:
    return NOTICE.read_text(encoding="utf-8")


def test_notice_exists() -> None:
    assert NOTICE.is_file(), "NOTICE file missing at repo root"


def test_notice_mentions_apache_license() -> None:
    text = _notice_text()
    assert "Apache License, Version 2.0" in text
    assert "http://www.apache.org/licenses/LICENSE-2.0" in text


def test_every_vendored_external_has_notice_entry() -> None:
    assert EXTERNAL_DIR.is_dir(), f"Vendored externals directory missing at {EXTERNAL_DIR}"
    text = _notice_text()
    externals = sorted(p.name for p in EXTERNAL_DIR.iterdir() if p.is_file())
    missing = [name for name in externals if name not in text]
    assert not missing, (
        f"NOTICE does not mention these vendored upstreams: {missing}. "
        "Add the source URL + license to NOTICE and register the file "
        "in scripts/release/audit_license_headers.py's VENDORED_EXTERNALS."
    )


def test_notice_documents_addition_procedure() -> None:
    """NOTICE must tell future contributors how to add a new upstream."""
    text = _notice_text()
    assert "audit_license_headers" in text, (
        "NOTICE must reference the audit script so future contributors "
        "know to register new vendored files there too."
    )
    assert "Adding a new vendored upstream" in text
