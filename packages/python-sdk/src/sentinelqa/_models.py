"""SDK-level result models.

These models are the SDK's public output shapes (the documentation). They wrap
the engine's typed domain entities but only expose what callers should
rely on. Pydantic v2 with ``model_config = ConfigDict(frozen=True)`` so
results are immutable and safe to share across threads / async tasks.

The engine entities used internally are imported lazily by the
:class:`Sentinel` facade so ``import sentinelqa`` stays cheap.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from engine.domain.finding import Finding, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.schema import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from engine.domain.test_run import RunStatus
from pydantic import BaseModel, ConfigDict, Field

# Severities considered "failures" for the SDK's ``failures`` view. The set
# matches the documentation — agents typically care about the severities that can
# block a release, plus high (which usually blocks under default policy).
_FAILURE_SEVERITIES: frozenset[str] = frozenset({"critical", "high"})


class QualityGate(BaseModel):
    """Release gate thresholds (the documentation ``policy:`` block).

    Mirrors :class:`engine.config.schema.PolicyConfig` but is the
    SDK-facing read-only view. Construct via :meth:`from_config` rather
    than directly so the field set tracks the config schema verbatim.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_quality_score: int = Field(ge=0, le=100)
    block_on_critical: bool
    block_on_high_security: bool
    max_flake_rate: float = Field(ge=0.0, le=1.0)
    allow_medium_a11y: bool
    max_failed_p1_flows: int = Field(ge=0)
    severity_penalty_high: float
    severity_penalty_medium: float
    severity_penalty_low: float

    @classmethod
    def from_config(cls, policy_config: Any) -> QualityGate:
        """Build a :class:`QualityGate` from a ``RootConfig.policy``."""

        return cls(
            min_quality_score=policy_config.min_quality_score,
            block_on_critical=policy_config.block_on_critical,
            block_on_high_security=policy_config.block_on_high_security,
            max_flake_rate=policy_config.max_flake_rate,
            allow_medium_a11y=policy_config.allow_medium_a11y,
            max_failed_p1_flows=policy_config.max_failed_p1_flows,
            severity_penalty_high=policy_config.severity_penalty_high,
            severity_penalty_medium=policy_config.severity_penalty_medium,
            severity_penalty_low=policy_config.severity_penalty_low,
        )


class Policy(BaseModel):
    """The safety + quality posture for a SentinelQA run.

    Combines the target allowlist + mode (the documentation ``target:`` /
    ``security:``) with the :class:`QualityGate`. Read-only.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: str
    allowed_hosts: tuple[str, ...]
    mode: Literal["safe", "authorized_destructive"]
    proof_of_authorization: Path | None
    quality_gate: QualityGate

    @classmethod
    def from_config(cls, root_config: Any) -> Policy:
        """Build a :class:`Policy` from a ``RootConfig`` instance."""

        return cls(
            base_url=str(root_config.target.base_url),
            allowed_hosts=tuple(root_config.target.allowed_hosts),
            mode=root_config.security.mode,
            proof_of_authorization=root_config.target.proof_of_authorization,
            quality_gate=QualityGate.from_config(root_config.policy),
        )


class AuditResult(BaseModel):
    """The result of a :meth:`Sentinel.audit` (or :meth:`Sentinel.run_plan`).

    Wire format is **stable** under ``schema_version`` — additive changes
    bump the minor; breaking shape changes bump the major and ship an
    ADR (our engineering rules, §40).
    """

    SCHEMA_VERSION: ClassVar[str] = RUN_SCHEMA_VERSION

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=RUN_SCHEMA_VERSION)
    run_id: str
    status: RunStatus
    release_decision: ReleaseDecision
    quality_score: float | None
    findings: tuple[Finding, ...]
    module_results: tuple[ModuleResult, ...]
    run_dir: Path
    started_at: datetime
    finished_at: datetime | None
    config_digest: str
    target_url: str
    modules_run: tuple[str, ...]

    # ------------------------------------------------------------------
    # Derived views
    # ------------------------------------------------------------------

    @property
    def passed(self) -> bool:
        """``True`` iff the run finished cleanly and the gate did not block.

        ``incomplete`` and ``unsafe_blocked`` are NOT passes — the documentation
        (evidence over magic): a partial run cannot claim success.
        """

        return self.status == "passed" and self.release_decision in {
            "pass",
            "pass_with_warnings",
        }

    @property
    def failures(self) -> tuple[Finding, ...]:
        """Findings at critical/high severity (the documentation).

        Order matches :attr:`findings` (already sorted by writer).
        """

        return tuple(f for f in self.findings if f.severity in _FAILURE_SEVERITIES)

    @property
    def blockers(self) -> tuple[Finding, ...]:
        """Findings at critical severity only."""

        return tuple(f for f in self.findings if f.severity == "critical")

    def findings_by_severity(self, severity: Severity) -> tuple[Finding, ...]:
        """Return findings at exactly ``severity``."""

        return tuple(f for f in self.findings if f.severity == severity)

    def findings_by_module(self, module: str) -> tuple[Finding, ...]:
        """Return findings emitted by ``module`` (e.g. ``"functional"``)."""

        return tuple(f for f in self.findings if f.module == module)

    # ------------------------------------------------------------------
    # Agent messages (the documentation, our engineering rules)
    # ------------------------------------------------------------------

    def to_agent_messages(self) -> tuple[dict[str, Any], ...]:
        """Return the agent-message stream for this run.

        Order is fixed so the same :class:`AuditResult` always serializes
        the same way (our engineering rules — reproducibility):

        1. ``run_summary`` — top-level run + decision + score.
        2. One ``finding`` message per finding, in writer order.
        3. ``blocker_summary`` — counts + IDs of any blocking findings.
        4. ``next_actions`` — deterministic suggested next steps.

        Each message carries ``schema_version`` so consumers can pin a
        downstream parser to a known shape.
        """

        from sentinelqa._agent_messages import (
            audit_result_to_agent_messages as _build,
        )

        return _build(self)


def build_audit_result(
    *,
    run_id: str,
    status: RunStatus,
    target_url: str,
    config_digest: str,
    started_at: datetime,
    finished_at: datetime | None,
    modules_run: Iterable[str],
    typed_findings: Iterable[Finding],
    typed_module_results: Iterable[ModuleResult],
    typed_score: QualityScore | None,
    typed_policy: PolicyDecision | None,
    run_dir: Path,
) -> AuditResult:
    """Assemble an :class:`AuditResult` from lifecycle context fields.

    Centralised so the sync and async facade paths construct results the
    same way and the test fixtures only have to stub one constructor.
    """

    if typed_policy is not None:
        decision: ReleaseDecision = typed_policy.release_decision
    elif status == "unsafe_blocked":
        decision = "unsafe_target_rejected"
    elif status == "dry_run" or status == "incomplete":
        decision = "inconclusive"
    elif status == "failed":
        decision = "blocked"
    else:
        decision = "pass"

    score_value: float | None = None
    if typed_score is not None:
        score_value = float(typed_score.total)

    return AuditResult(
        run_id=run_id,
        status=status,
        release_decision=decision,
        quality_score=score_value,
        findings=tuple(typed_findings),
        module_results=tuple(typed_module_results),
        run_dir=run_dir,
        started_at=started_at,
        finished_at=finished_at,
        config_digest=config_digest,
        target_url=target_url,
        modules_run=tuple(modules_run),
    )


__all__ = [
    "AGENT_MESSAGE_SCHEMA_VERSION",
    "AuditResult",
    "Policy",
    "QualityGate",
    "build_audit_result",
]
