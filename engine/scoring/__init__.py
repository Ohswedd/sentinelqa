"""Quality scoring (, our product spec, our engineering rules).

Reproducible release-confidence score derived from typed findings +
module results + policy config. Every value the writer persists is a
pure function of these inputs — no time, no randomness, no I/O — so
the same inputs always yield byte-identical ``score.json``.

Public surface:

- :func:`compute_score` — turn findings + module results + policy into
 :class:`engine.domain.quality_score.QualityScore`.
- :func:`compute_blockers` — apply blocker rules from our engineering rules.
- :func:`decide` — translate score + blockers + run status into
 :class:`engine.domain.policy_decision.PolicyDecision`.
- :func:`apply_policy_gate` — orchestrator helper combining the above
 and stamping ``ctx.quality_gate_passed`` for the exit-code mapping.
- :func:`register_scoring_hooks` — wire the lifecycle hooks for
 ``CALCULATE_QUALITY_SCORE`` and ``APPLY_QUALITY_GATES``.
"""

from __future__ import annotations

from engine.scoring.blockers import Blocker, compute_blockers
from engine.scoring.decision import decide
from engine.scoring.model import (
    COMPONENT_AXES,
    CRITICAL_PENALTY,
    DEFAULT_WEIGHTS,
    PRIORITY_TAG_PATTERN,
    PenaltyTable,
    compute_score,
    derive_penalty_table,
    finding_priority,
)
from engine.scoring.policy_gate import (
    apply_policy_gate,
    register_scoring_hooks,
)

__all__ = [
    "Blocker",
    "COMPONENT_AXES",
    "CRITICAL_PENALTY",
    "DEFAULT_WEIGHTS",
    "PRIORITY_TAG_PATTERN",
    "PenaltyTable",
    "apply_policy_gate",
    "compute_blockers",
    "compute_score",
    "decide",
    "derive_penalty_table",
    "finding_priority",
    "register_scoring_hooks",
]
