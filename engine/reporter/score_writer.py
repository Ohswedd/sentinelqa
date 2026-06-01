"""``score.json`` writer.

Persists the quality score with **deterministic float formatting** so the
JSON output is byte-stable across runs (our engineering rules — score must be
reproducible). owns the actual score *computation*; this module
only writes whatever is handed to it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.orchestrator.artifacts import ArtifactDirectory

SCORE_REPORT_SCHEMA_VERSION: str = "1"

# Component axes persisted in `score.json.components/weights`. Listed
# explicitly so the schema and writer evolve together. Missing axes are
# persisted as 0.0 so reviewers always see the full surface.
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

# Severity buckets persisted in `score.json.severity_penalties`. Same
# rationale as :data:`COMPONENT_AXES`.
SEVERITY_BUCKETS: Final[tuple[str, ...]] = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
)

# Default policy values mirror the documentation and our engineering rules. They are
# applied when the caller hasn't yet wired the real policy (+),
# so the file always has a complete record.
DEFAULT_POLICY: Final[Mapping[str, Any]] = {
    "min_quality_score": 80.0,
    "block_on_critical": True,
    "block_on_high_security": True,
    "max_failed_p1_flows": 0,
    "max_flake_rate": 0.05,
}


def write_score(
    artifact_dir: ArtifactDirectory,
    *,
    run_id: str,
    score: QualityScore | None,
    policy_decision: PolicyDecision | None,
    policy_config: Mapping[str, Any] | None = None,
    release_decision: ReleaseDecision | None = None,
    filename: str = "score.json",
) -> Path:
    """Serialize the score envelope and return the path.

    ``score`` may be ``None`` (for unsafe_blocked / dry_run runs); the
    writer then sets ``total=None`` and zero-fills the per-axis fields.

    ``policy_decision`` supplies the canonical release decision and the
    blocking-finding list. If absent, callers may pass an explicit
    ``release_decision`` (e.g. derived by the orchestrator).
    """

    if release_decision is None:
        release_decision = (
            policy_decision.release_decision if policy_decision is not None else "inconclusive"
        )
    blockers: tuple[str, ...] = policy_decision.blocked_by if policy_decision is not None else ()

    envelope: dict[str, Any] = {
        "schema_version": SCORE_REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "total": _quantize_total(score.total) if score is not None else None,
        "components": _coerce_axes(score.components if score is not None else {}),
        "weights": _coerce_axes(score.weights if score is not None else {}),
        "severity_penalties": _coerce_penalties(
            score.severity_penalties_applied if score is not None else {}
        ),
        "blockers": list(blockers),
        "release_decision": release_decision,
        "policy": _coerce_policy(policy_config),
    }
    return artifact_dir.write_json(filename, envelope)


def _quantize_total(value: float) -> float:
    """Round to 2 decimals so JSON serialization is byte-stable."""

    return round(float(value), 2)


def _coerce_axes(values: Mapping[str, float]) -> dict[str, float]:
    """Project an arbitrary axis-mapping onto :data:`COMPONENT_AXES`."""

    out: dict[str, float] = {}
    for axis in COMPONENT_AXES:
        raw = float(values.get(axis, 0.0))
        out[axis] = round(raw, 4)
    return out


def _coerce_penalties(values: Mapping[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for bucket in SEVERITY_BUCKETS:
        raw = float(values.get(bucket, 0.0))
        out[bucket] = round(raw, 4)
    return out


def _coerce_policy(values: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge caller-provided policy onto :data:`DEFAULT_POLICY`."""

    out: dict[str, Any] = dict(DEFAULT_POLICY)
    if values:
        for key in DEFAULT_POLICY:
            if key in values:
                out[key] = _coerce_policy_value(key, values[key])
    return out


def _coerce_policy_value(key: str, raw: Any) -> Any:
    """Coerce a policy value to the schema-expected type."""

    if key == "block_on_critical" or key == "block_on_high_security":
        return bool(raw)
    if key == "max_failed_p1_flows":
        return int(raw)
    if key == "max_flake_rate":
        return round(float(raw), 4)
    if key == "min_quality_score":
        return round(float(raw), 2)
    return raw


def known_finding_ids(blockers: Iterable[str]) -> tuple[str, ...]:
    """Return blockers in insertion order (helper for the orchestrator)."""

    return tuple(blockers)


__all__ = [
    "COMPONENT_AXES",
    "DEFAULT_POLICY",
    "SCORE_REPORT_SCHEMA_VERSION",
    "SEVERITY_BUCKETS",
    "known_finding_ids",
    "write_score",
]
