"""Quality-score computation (task 14.01).

Builds :class:`engine.domain.quality_score.QualityScore` from typed
findings + module results + the configured policy. The function is
deterministic by construction: no time, no randomness, no I/O.
Floats are rounded half-to-even (Python's :func:`round`) so JSON
serialization is byte-stable across runs (CLAUDE.md §25).

Component scoring
-----------------

Each PRD §19.1 component (functional, security, performance,
accessibility, api, visual, llm_audit) gets a per-module sub-score
in [0, 100]:

    component_score = max(0, 100 - sum(penalty per finding in that module))

The eighth axis is `flake_risk`, computed from the runner-reported
`flake_rate` metric on each module result:

    rate          = mean(flake_rate across reporting modules) or 0
    flake_score   = 100 * (1 - min(1, rate / policy.max_flake_rate))

The aggregate `total` is the weighted average of the eight axis scores
clamped to [0, 100]. Default weights match PRD §19.1.

Severity penalties
------------------

The penalty per finding comes from :func:`derive_penalty_table` which
reads the PolicyConfig severity-penalty fields (defaulting to the
midpoint of the PRD §19.2 ranges). Critical findings carry a fixed
penalty of :data:`CRITICAL_PENALTY` so the numeric score still
reflects severity even when `policy.block_on_critical` would otherwise
blocked release.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from engine.config.schema import PolicyConfig
from engine.domain.finding import Finding, Severity
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult
from engine.domain.quality_score import QualityScore

# The eight axes persisted in `score.json` (see
# ``engine.reporter.score_writer.COMPONENT_AXES``). Listed explicitly so
# the score and the writer evolve together — adding a ninth axis must
# update both files plus the schema.
COMPONENT_AXES: Final[tuple[str, ...]] = (
    "functional",
    "security",
    "performance",
    "accessibility",
    "api",
    "visual",
    "llm_audit",
    "flake_risk",
)

# Default weights from PRD §19.1. Sum to 1.0.
DEFAULT_WEIGHTS: Final[Mapping[str, float]] = {
    "functional": 0.30,
    "security": 0.20,
    "performance": 0.15,
    "accessibility": 0.10,
    "api": 0.10,
    "visual": 0.05,
    "llm_audit": 0.05,
    "flake_risk": 0.05,
}

# Critical penalty is fixed (PRD §19.2 says "Blocks release"; the
# numeric value here only affects the score for callers that disable
# `block_on_critical`).
CRITICAL_PENALTY: Final[float] = 30.0

# Severity buckets persisted in `score.json.severity_penalties` (the
# writer iterates this exact tuple).
SEVERITY_BUCKETS: Final[tuple[Severity, ...]] = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
)

# Recognised priority tags in a finding title. Phase 10 generated specs
# bake the tag into the test name; the Finding model doesn't yet carry
# a `priority` field (Phase 14 ADR-0019 records this MVP shortcut).
PRIORITY_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(r"@(p[0-3])\b", re.IGNORECASE)


@dataclass(frozen=True)
class PenaltyTable:
    """Per-severity penalty values used during scoring."""

    critical: float
    high: float
    medium: float
    low: float
    info: float = 0.0

    def for_severity(self, severity: Severity) -> float:
        return getattr(self, severity)

    def as_mapping(self) -> Mapping[str, float]:
        return {
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "info": self.info,
        }


def derive_penalty_table(policy: PolicyConfig) -> PenaltyTable:
    """Read the per-severity penalty values from policy config."""

    return PenaltyTable(
        critical=CRITICAL_PENALTY,
        high=float(policy.severity_penalty_high),
        medium=float(policy.severity_penalty_medium),
        low=float(policy.severity_penalty_low),
        info=0.0,
    )


def finding_priority(finding: Finding) -> str | None:
    """Return the lowercased priority tag (``"p0".."p3"``) if present.

    Looks at the finding title first (Phase 10 specs embed the tag in
    the test name) and falls back to the description.
    """

    for source in (finding.title, finding.description):
        if source is None:
            continue
        match = PRIORITY_TAG_PATTERN.search(source)
        if match:
            return match.group(1).lower()
    return None


def compute_score(
    findings: Iterable[Finding],
    module_results: Iterable[ModuleResult],
    *,
    policy: PolicyConfig,
    run_id: str,
    id_generator: IdGenerator | None = None,
    weights: Mapping[str, float] | None = None,
) -> QualityScore:
    """Compute the reproducible :class:`QualityScore` for a run.

    ``id_generator`` is optional — the SCR id never reaches disk
    (``score.json`` doesn't carry it), so randomness here has no
    observable effect on artifact bytes.
    """

    findings_t = tuple(findings)
    module_results_t = tuple(module_results)
    weights_map = dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS)
    _validate_weights(weights_map)

    penalty_table = derive_penalty_table(policy)
    components = _component_scores(findings_t, penalty_table)
    components["flake_risk"] = _flake_risk_score(module_results_t, policy)

    total_raw = sum(components[axis] * weights_map.get(axis, 0.0) for axis in COMPONENT_AXES)
    total = max(0.0, min(100.0, total_raw))

    severity_penalties = _severity_penalties_breakdown(findings_t, penalty_table)

    return QualityScore(
        id=(id_generator or IdGenerator()).new("SCR"),
        run_id=run_id,
        total=round(total, 2),
        components={axis: round(components[axis], 4) for axis in COMPONENT_AXES},
        weights={axis: round(weights_map.get(axis, 0.0), 4) for axis in COMPONENT_AXES},
        severity_penalties_applied=severity_penalties,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_weights(weights: Mapping[str, float]) -> None:
    for axis in COMPONENT_AXES:
        if axis not in weights:
            raise ValueError(f"weights is missing required axis {axis!r}.")
        if weights[axis] < 0.0:
            raise ValueError(f"weights[{axis!r}] must be >= 0; got {weights[axis]}.")


def _component_scores(
    findings: tuple[Finding, ...],
    penalty_table: PenaltyTable,
) -> dict[str, float]:
    """Per-module sub-scores in [0, 100], one entry per non-flake axis.

    Missing axes (modules with zero findings) default to 100 so a clean
    run scores 100 across the board.
    """

    by_module: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_module[f.module].append(f)

    out: dict[str, float] = {}
    for axis in COMPONENT_AXES:
        if axis == "flake_risk":
            continue
        module_findings = by_module.get(axis, [])
        penalty_total = sum(penalty_table.for_severity(f.severity) for f in module_findings)
        out[axis] = max(0.0, 100.0 - penalty_total)
    return out


def _flake_risk_score(
    module_results: tuple[ModuleResult, ...],
    policy: PolicyConfig,
) -> float:
    """Translate runner-reported flake_rate metrics into a 0..100 score.

    ``flake_rate`` is the fraction of executions that passed on retry
    (Phase 08 aggregator). If no module reports it, we treat the run as
    free of flake (100). When ``policy.max_flake_rate`` is zero, any
    non-zero rate scores 0.
    """

    rates: list[float] = []
    for mr in module_results:
        if "flake_rate" in mr.metrics:
            rates.append(max(0.0, float(mr.metrics["flake_rate"])))
    if not rates:
        return 100.0
    avg = sum(rates) / len(rates)
    max_flake = float(policy.max_flake_rate)
    if max_flake <= 0.0:
        return 0.0 if avg > 0.0 else 100.0
    ratio = min(1.0, avg / max_flake)
    return max(0.0, 100.0 * (1.0 - ratio))


def _severity_penalties_breakdown(
    findings: tuple[Finding, ...],
    penalty_table: PenaltyTable,
) -> dict[str, float]:
    """Return the total penalty applied per severity bucket."""

    out: dict[str, float] = {bucket: 0.0 for bucket in SEVERITY_BUCKETS}
    for f in findings:
        penalty = penalty_table.for_severity(f.severity)
        out[f.severity] = round(out[f.severity] + penalty, 4)
    return out


__all__ = [
    "COMPONENT_AXES",
    "CRITICAL_PENALTY",
    "DEFAULT_WEIGHTS",
    "PRIORITY_TAG_PATTERN",
    "PenaltyTable",
    "SEVERITY_BUCKETS",
    "compute_score",
    "derive_penalty_table",
    "finding_priority",
]
