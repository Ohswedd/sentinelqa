"""Finding attestation entity (v1.7.0, phase 37).

Each finding may carry an :class:`Attestation` that records *who decided
this and how*: the check that produced it, the rule (and rule version)
that fired, and the exact commit of SentinelQA running at the time.
This closes the "who decided this?" loop for auditors who need to
reproduce a verdict months later.

Attestation is intentionally optional. Modules that have not yet been
threaded for provenance keep emitting findings without one; tools that
expect provenance must guard accordingly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_validator

from engine.domain.base import SentinelModel


class Attestation(SentinelModel):
    """Provenance metadata recorded alongside a finding."""

    check_name: str = Field(min_length=1, max_length=128)
    """Stable identifier of the check that emitted the finding.

    Format is module-scoped, e.g. ``security.headers.csp_missing`` or
    ``a11y.axe.color-contrast``. The value must be stable across runs
    so dedup + history correlation work.
    """

    rule_id: str = Field(min_length=1, max_length=128)
    """Rule identifier inside the check.

    Typically the upstream rule id (axe rule, CWE, SAST rule), or — when
    there is no upstream — a SentinelQA-coined id like ``cookie-missing-secure``.
    """

    rule_version: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._\-+]+$")
    """Version of the rule / ruleset that fired.

    Free-form per check (semver, axe-core version, OWASP doc rev, etc.)
    but constrained to a single token so it survives round-tripping
    through JSON and shell quoting.
    """

    sentinelqa_commit: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-f]+$")
    """Lowercase hex git commit of SentinelQA at decision time."""

    decided_at: datetime
    """Timezone-aware UTC instant when the rule fired."""

    @field_validator("decided_at")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Attestation.decided_at must be timezone-aware (UTC).")
        return value.astimezone(UTC)


__all__ = ["Attestation"]
