"""Verify the Phase-00 redaction stub is importable and refuses to run.

Phase 01 (`plans/phase-01-core-domain-config/05-redaction.md`) replaces the
stub with the real implementation. These tests will be expanded to cover the
real behavior at that point; today they only enforce CLAUDE.md §37 — the
stub must not silently succeed.
"""

from __future__ import annotations

import pytest
from engine.policy.redaction import redact


def test_redact_is_importable() -> None:
    """The symbol must exist so other phases can wire it in."""
    assert callable(redact)


def test_redact_raises_until_phase_01() -> None:
    """Calling the stub must fail explicitly (no fake completion)."""
    with pytest.raises(NotImplementedError) as exc:
        redact("token=abc123")
    assert "Phase 01" in str(exc.value)
