"""Human-review gating tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.banner import BannerStatus
from engine.healer.gating import decide_auto_apply
from engine.healer.models import RepairKind, RepairProposal


def _proposal(
    *,
    kind: RepairKind,
    confidence: float = 0.95,
    requires_review: bool = False,
) -> RepairProposal:
    gen = IdGenerator()
    return RepairProposal(
        id=gen.new("RPR"),
        kind=kind,
        target_test="a.spec.ts",
        original_behavior="x",
        proposed_change="y",
        confidence=confidence,
        reason="r",
        evidence=(Evidence(id=gen.new("EVD"), type="source_ref", path=Path("a.spec.ts")),),
        requires_human_review=requires_review,
        unified_diff="--- a\n+++ b\n@@\n-x\n+y\n",
    )


_HEALTHY_BANNER = BannerStatus(
    has_banner=True,
    generated_at=datetime(2026, 5, 1, tzinfo=UTC),
    last_modified=datetime(2026, 5, 1, tzinfo=UTC),
    hand_edited=False,
    reason="generated and untouched",
)
_HAND_EDITED = BannerStatus(
    has_banner=False,
    generated_at=None,
    last_modified=datetime(2026, 5, 1, tzinfo=UTC),
    hand_edited=True,
    reason="no banner detected",
)


def test_off_mode_never_applies() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="locator"),
        banner_status=_HEALTHY_BANNER,
        mode="off",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is False
    assert "off" in decision.reason


def test_safe_mode_applies_locator_above_threshold() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="locator", confidence=0.95),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is True


def test_safe_mode_refuses_assertion() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="assertion", confidence=0.99),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is False
    assert "not permitted" in decision.reason


def test_safe_mode_refuses_fixture() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="fixture", confidence=0.99),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is False


def test_aggressive_mode_allows_fixture() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="fixture", confidence=0.99),
        banner_status=_HEALTHY_BANNER,
        mode="aggressive",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is True


def test_aggressive_mode_refuses_assertion_without_allow_weaken() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="assertion", confidence=0.99),
        banner_status=_HEALTHY_BANNER,
        mode="aggressive",
        auto_apply_threshold=0.9,
        allow_weaken=False,
    )
    assert decision.should_apply is False
    assert "allow-weaken" in decision.reason


def test_aggressive_mode_with_allow_weaken_applies_assertion() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="assertion", confidence=0.99),
        banner_status=_HEALTHY_BANNER,
        mode="aggressive",
        auto_apply_threshold=0.9,
        allow_weaken=True,
    )
    assert decision.should_apply is True


def test_hand_edited_spec_refuses_regardless_of_mode() -> None:
    for mode in ("safe", "aggressive"):
        decision = decide_auto_apply(
            proposal=_proposal(kind="locator"),
            banner_status=_HAND_EDITED,
            mode=mode,  # type: ignore[arg-type]
            auto_apply_threshold=0.9,
        )
        assert decision.should_apply is False
        assert "hand-edited" in decision.reason


def test_requires_human_review_flag_refuses_apply() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="locator", requires_review=True),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is False
    assert "requires_human_review" in decision.reason


def test_confidence_below_threshold_refuses_apply() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="locator", confidence=0.85),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is False
    assert "confidence" in decision.reason


def test_decision_reason_is_descriptive_on_apply() -> None:
    decision = decide_auto_apply(
        proposal=_proposal(kind="locator", confidence=0.95),
        banner_status=_HEALTHY_BANNER,
        mode="safe",
        auto_apply_threshold=0.9,
    )
    assert decision.should_apply is True
    assert "locator" in decision.reason
    assert "0.95" in decision.reason or "0.90" in decision.reason or "0.9" in decision.reason
