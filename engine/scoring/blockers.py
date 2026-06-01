"""Blocker computation (task 14.02, our engineering rules).

A blocker is a finding (or a structural condition) that forces the
release decision to ``blocked`` regardless of the numeric score.
Rules:

1. Any ``critical`` severity finding when ``policy.block_on_critical``.
2. Any ``high`` severity finding in the ``security`` module when
   ``policy.block_on_high_security``.
3. Any failed test in a P0 functional flow (detected via the
   ``@p0`` tag in the finding title — see :func:`engine.scoring.model.finding_priority`).
4. More than ``policy.max_failed_p1_flows`` P1 functional failures.

Each :class:`Blocker` carries the rule name, the originating finding
ID (or ``None`` for structural rules), and a human-readable
justification suitable for `score.json` + the explain report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding
from engine.scoring.model import finding_priority


@dataclass(frozen=True)
class Blocker:
    """A single reason a run is blocked."""

    rule_name: str
    finding_id: str | None
    justification: str


def compute_blockers(
    findings: Iterable[Finding],
    *,
    policy: PolicyConfig,
) -> list[Blocker]:
    """Apply the blocker rules and return the resulting list.

    Findings are processed in lexicographic ID order so the output is
    deterministic regardless of input ordering.
    """

    sorted_findings = sorted(findings, key=lambda f: f.id)
    blockers: list[Blocker] = []

    if policy.block_on_critical:
        for f in sorted_findings:
            if f.severity == "critical":
                blockers.append(
                    Blocker(
                        rule_name="critical_finding",
                        finding_id=f.id,
                        justification=(
                            f"Critical finding {f.id} in module {f.module!r}: {f.title}. "
                            "policy.block_on_critical=true."
                        ),
                    )
                )

    if policy.block_on_high_security:
        for f in sorted_findings:
            if f.module == "security" and f.severity == "high":
                blockers.append(
                    Blocker(
                        rule_name="security_high",
                        finding_id=f.id,
                        justification=(
                            f"High-severity security finding {f.id}: {f.title}. "
                            "policy.block_on_high_security=true."
                        ),
                    )
                )

    p0_failures = [
        f for f in sorted_findings if f.module == "functional" and finding_priority(f) == "p0"
    ]
    for f in p0_failures:
        blockers.append(
            Blocker(
                rule_name="p0_flow_failed",
                finding_id=f.id,
                justification=(
                    f"P0 functional flow failed: {f.id} — {f.title}. "
                    "P0 failures always block release."
                ),
            )
        )

    p1_failures = [
        f for f in sorted_findings if f.module == "functional" and finding_priority(f) == "p1"
    ]
    if len(p1_failures) > policy.max_failed_p1_flows:
        blockers.append(
            Blocker(
                rule_name="too_many_p1_failures",
                finding_id=None,
                justification=(
                    f"{len(p1_failures)} P1 functional failures observed; "
                    f"policy.max_failed_p1_flows={policy.max_failed_p1_flows}."
                ),
            )
        )

    return blockers


__all__ = ["Blocker", "compute_blockers"]
