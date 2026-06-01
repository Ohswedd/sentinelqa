"""Auto-apply gating policy (Phase 20.06, our engineering rules).

The Healer never decides on its own whether a proposal applies. This
module computes :class:`AutoApplyDecision` for one proposal given:

- the operator's ``policy.healer.auto_apply`` posture (``off`` / ``safe``
  / ``aggressive``),
- the spec's banner status (hand-edited specs are always refused),
- the proposal's confidence vs the configured auto-apply threshold,
- the proposal's ``kind`` (``assertion`` repairs are aggressive-only),
- the operator's ``--allow-weaken`` opt-in (CLI surface).

Hand-edited specs are refused regardless of mode. ``off`` mode never
applies. ``safe`` mode applies ``locator`` and ``wait`` repairs at or
above the threshold, but never ``assertion`` ones. ``aggressive``
mode adds ``fixture`` and ``assertion`` repairs but ``assertion``
still requires ``allow_weaken=True``.

All decisions carry a human-readable reason — the CLI logs that
reason in ``audit.log`` on every applied repair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engine.healer.banner import BannerStatus
from engine.healer.models import RepairKind, RepairProposal

AutoApplyMode = Literal["off", "safe", "aggressive"]


@dataclass(frozen=True)
class AutoApplyDecision:
    """Outcome of the gating check for one proposal."""

    should_apply: bool
    reason: str
    """One sentence; copied to the audit log on apply or skip."""


# Kinds permitted by each mode. ``assertion`` is the special case —
# even in ``aggressive`` it requires ``allow_weaken=True``.
_SAFE_KINDS: frozenset[RepairKind] = frozenset({"locator", "wait"})
_AGGRESSIVE_KINDS: frozenset[RepairKind] = frozenset({"locator", "wait", "fixture", "assertion"})


def decide_auto_apply(
    *,
    proposal: RepairProposal,
    banner_status: BannerStatus,
    mode: AutoApplyMode,
    auto_apply_threshold: float,
    allow_weaken: bool = False,
) -> AutoApplyDecision:
    """Return whether ``proposal`` should be auto-applied.

    The function is pure — the CLI uses the result to decide whether to
    write the patch and to log to ``audit.log``.
    """

    if mode == "off":
        return AutoApplyDecision(
            should_apply=False,
            reason="auto_apply mode is 'off' — proposals are review-only.",
        )

    if banner_status.hand_edited:
        return AutoApplyDecision(
            should_apply=False,
            reason=f"target spec is hand-edited: {banner_status.reason}",
        )

    if proposal.requires_human_review:
        return AutoApplyDecision(
            should_apply=False,
            reason="proposal carries requires_human_review=True.",
        )

    allowed_kinds = _SAFE_KINDS if mode == "safe" else _AGGRESSIVE_KINDS
    if proposal.kind not in allowed_kinds:
        return AutoApplyDecision(
            should_apply=False,
            reason=(f"kind {proposal.kind!r} is not permitted in auto_apply mode " f"{mode!r}."),
        )

    if proposal.kind == "assertion" and not allow_weaken:
        return AutoApplyDecision(
            should_apply=False,
            reason=("assertion repairs require --allow-weaken even in aggressive " "mode."),
        )

    if proposal.confidence < auto_apply_threshold:
        return AutoApplyDecision(
            should_apply=False,
            reason=(
                f"confidence {proposal.confidence:.2f} below auto_apply_threshold "
                f"{auto_apply_threshold:.2f}."
            ),
        )

    return AutoApplyDecision(
        should_apply=True,
        reason=(
            f"mode={mode}, kind={proposal.kind}, confidence={proposal.confidence:.2f} "
            f"≥ threshold {auto_apply_threshold:.2f}."
        ),
    )


__all__ = ["AutoApplyDecision", "AutoApplyMode", "decide_auto_apply"]
