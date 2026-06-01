"""Wire-format models for :class:`modules.security.SecurityModule`.

These mirror what the module persists under ``<run-dir>/security/`` so
the Reporter ( / 15) and SDK can re-load a run
without re-executing it. The schema version is bumped under an ADR
(see ADR-0018) and is enforced at parse time.
"""

from __future__ import annotations

from typing import ClassVar

from engine.domain.base import SentinelModel
from engine.domain.finding import Severity
from pydantic import Field, field_validator

SECURITY_RESULT_SCHEMA_VERSION: str = "1"
"""Bump under an ADR. Owned by Phase 13."""


CheckName = str  # one of: "headers", "cookies", "cors", "csrf", "xss_reflected",
# "xss_stored", "sqli", "idor", "frontend_secrets", "dependency_scan", "sast"


class SecurityIssue(SentinelModel):
    """One observation by a security check.

    The ``rule_id`` field matches an entry in :mod:`modules.security.rules`
    so the finding writer (:mod:`engine.reporter.findings_writer`) and the
    SARIF writer can attach documentation links and SARIF metadata.
    """

    SCHEMA_VERSION: ClassVar[str] = SECURITY_RESULT_SCHEMA_VERSION

    rule_id: str = Field(min_length=1, max_length=128)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=8000)
    route: str | None = Field(default=None, max_length=2048)
    evidence: dict[str, object] = Field(default_factory=dict)
    recommendation: str | None = Field(default=None, max_length=4000)
    schema_version: str = Field(default=SECURITY_RESULT_SCHEMA_VERSION)

    @field_validator("rule_id")
    @classmethod
    def _check_rule_id(cls, value: str) -> str:
        if not value.startswith("SEC-"):
            raise ValueError("SecurityIssue.rule_id must start with 'SEC-'.")
        return value


class SecurityCheckResult(SentinelModel):
    """Result of one named security check (e.g. ``headers``)."""

    SCHEMA_VERSION: ClassVar[str] = SECURITY_RESULT_SCHEMA_VERSION

    check: CheckName = Field(min_length=1, max_length=64)
    targets_scanned: int = Field(default=0, ge=0)
    issues: tuple[SecurityIssue, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(default=0, ge=0)
    skipped: bool = False
    skipped_reason: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SECURITY_RESULT_SCHEMA_VERSION)


class SecurityRunOutcome(SentinelModel):
    """Top-level wire model written to ``security/index.json``."""

    SCHEMA_VERSION: ClassVar[str] = SECURITY_RESULT_SCHEMA_VERSION

    checks: tuple[SecurityCheckResult, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(default=0, ge=0)
    incomplete: bool = False
    schema_version: str = Field(default=SECURITY_RESULT_SCHEMA_VERSION)


__all__ = [
    "SECURITY_RESULT_SCHEMA_VERSION",
    "CheckName",
    "SecurityIssue",
    "SecurityCheckResult",
    "SecurityRunOutcome",
]
