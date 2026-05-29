"""Healer module — propose safe test-side repairs (PRD §9.6, CLAUDE.md §23).

The Healer is conservative by design. It proposes locator updates, wait
condition improvements, and fixture refreshes; it never weakens
assertions, never edits production code, never removes a test. Each
proposal carries:

- ``original_behavior`` / ``proposed_change`` — what changes.
- ``confidence`` — 0..1 scalar derived deterministically from the match
  quality, NOT from a model call.
- ``reason`` and ``evidence`` — first-class so a reviewer can judge.
- ``requires_human_review`` — set conservatively per gating policy.
- ``unified_diff`` — the literal patch a CI/agent would apply.

The orchestrator (PRD §9.5 → §9.6) invokes the Healer for failures the
Analyzer categorized as ``test_bug``. Other categories (app bugs,
environment failures, security findings) are out of scope: the Healer
must not paper over app behavior.
"""

from __future__ import annotations

from engine.healer.banner import (
    BannerStatus,
    detect_banner_status,
)
from engine.healer.diff import (
    AssertionWeakeningError,
    assert_no_assertion_weakening,
    unified_diff_for,
)
from engine.healer.fixture_repair import propose_fixture_repair
from engine.healer.gating import (
    AutoApplyDecision,
    AutoApplyMode,
    decide_auto_apply,
)
from engine.healer.locator_repair import propose_locator_repair
from engine.healer.models import (
    RepairKind,
    RepairProposal,
)
from engine.healer.pipeline import Healer, HealerContext, HealerInputs
from engine.healer.wait_repair import propose_wait_repair
from engine.healer.writer import (
    HEALER_INDEX_FILENAME,
    write_index,
    write_proposal,
)

__all__ = [
    "AssertionWeakeningError",
    "AutoApplyDecision",
    "AutoApplyMode",
    "BannerStatus",
    "HEALER_INDEX_FILENAME",
    "Healer",
    "HealerContext",
    "HealerInputs",
    "RepairKind",
    "RepairProposal",
    "assert_no_assertion_weakening",
    "decide_auto_apply",
    "detect_banner_status",
    "propose_fixture_repair",
    "propose_locator_repair",
    "propose_wait_repair",
    "unified_diff_for",
    "write_index",
    "write_proposal",
]
