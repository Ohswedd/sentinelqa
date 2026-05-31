"""Typed inputs / outputs for the compliance module (Phase 34)."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

COMPLIANCE_SCHEMA_VERSION = "1"
"""Wire format of the ``compliance/<sub-check>.json`` summaries."""


GdprCategory = Literal[
    "cookies-before-consent",
    "asymmetric-consent",
    "consent-banner-missing",
]

CcpaCategory = Literal[
    "do-not-sell-link-missing",
    "do-not-sell-link-opt-out-missing",
]

Soc2Category = Literal[
    "trail-missing",
    "trail-not-jsonl",
    "trail-non-monotonic",
    "trail-secret-leak",
    "trail-missing-safety-decision",
    "trail-missing-module-event",
    "trail-missing-artifact-event",
    "trail-missing-llm-event",
    "trail-missing-vault-event",
]

Wcag22SignalCategory = Literal[
    "focus-obscured",
    "target-size-min",
    "dragging-movements",
    "redundant-entry",
    "accessible-authentication",
]


# ---------------------------------------------------------------------------
# GDPR
# ---------------------------------------------------------------------------


class GdprCookie(BaseModel):
    """One ``Set-Cookie`` observation on the first page-load."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=256)
    domain: str = Field(default="", max_length=256)
    essential: bool = False
    """Operators flag known-essential cookies (session, csrf token, ...)
    so the detector ignores them when checking cookies-before-consent."""


class GdprBannerSignal(BaseModel):
    """DOM-derived signal: was a consent banner detected on first load?"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    present: bool
    accept_one_click: bool = True
    reject_one_click: bool = True
    selector: str = Field(default="", max_length=2_048)


class GdprPageSignals(BaseModel):
    """Aggregate GDPR signals for one route (the entry route in practice)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route: str = Field(min_length=1, max_length=2_048)
    banner: GdprBannerSignal
    cookies_on_first_load: tuple[GdprCookie, ...] = Field(default_factory=tuple, max_length=200)


class GdprIssue(BaseModel):
    """One GDPR check finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: GdprCategory
    route: str = Field(min_length=1, max_length=2_048)
    description: str = Field(min_length=1, max_length=2_000)
    cookie_name: str = Field(default="", max_length=256)
    compliance_id: str = Field(min_length=1, max_length=128)


class GdprCheckReport(BaseModel):
    """Summary of a GDPR check run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = COMPLIANCE_SCHEMA_VERSION

    schema_version: str = Field(default=COMPLIANCE_SCHEMA_VERSION)
    pages_checked: int = Field(ge=0)
    issues: tuple[GdprIssue, ...] = Field(default_factory=tuple, max_length=500)


# ---------------------------------------------------------------------------
# CCPA
# ---------------------------------------------------------------------------


class CcpaPageSignal(BaseModel):
    """One page worth of CCPA-relevant signals (link presence + target)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route: str = Field(min_length=1, max_length=2_048)
    link_text: str = Field(default="", max_length=256)
    link_href: str = Field(default="", max_length=2_048)
    link_followed: bool = False
    target_has_opt_out_form: bool = False


class CcpaIssue(BaseModel):
    """One CCPA check finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: CcpaCategory
    route: str = Field(min_length=1, max_length=2_048)
    description: str = Field(min_length=1, max_length=2_000)
    compliance_id: str = Field(min_length=1, max_length=128)


class CcpaCheckReport(BaseModel):
    """Summary of a CCPA check run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = COMPLIANCE_SCHEMA_VERSION

    schema_version: str = Field(default=COMPLIANCE_SCHEMA_VERSION)
    pages_checked: int = Field(ge=0)
    issues: tuple[CcpaIssue, ...] = Field(default_factory=tuple, max_length=500)


# ---------------------------------------------------------------------------
# SOC 2 trail
# ---------------------------------------------------------------------------


class Soc2GateResult(BaseModel):
    """Per-gate result for the SOC 2 trail check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate: str = Field(min_length=1, max_length=128)
    passed: bool
    detail: str = Field(default="", max_length=2_000)


class Soc2Issue(BaseModel):
    """One SOC 2 trail finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Soc2Category
    description: str = Field(min_length=1, max_length=2_000)
    compliance_id: str = Field(min_length=1, max_length=128)


class Soc2CheckReport(BaseModel):
    """Aggregate result of the SOC 2 audit-trail gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = COMPLIANCE_SCHEMA_VERSION

    schema_version: str = Field(default=COMPLIANCE_SCHEMA_VERSION)
    trail_path: str = Field(default="", max_length=2_048)
    entries_read: int = Field(ge=0)
    gates: tuple[Soc2GateResult, ...] = Field(default_factory=tuple, max_length=20)
    issues: tuple[Soc2Issue, ...] = Field(default_factory=tuple, max_length=200)

    @property
    def all_gates_passed(self) -> bool:
        return all(gate.passed for gate in self.gates)


# ---------------------------------------------------------------------------
# WCAG 2.2 (deterministic, signal-driven)
# ---------------------------------------------------------------------------


class Wcag22Issue(BaseModel):
    """Translated WCAG 2.2 finding emitted by the compliance module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Wcag22SignalCategory
    success_criterion: str = Field(min_length=1, max_length=16)
    route: str = Field(default="/", max_length=2_048)
    selector: str = Field(default="", max_length=2_048)
    description: str = Field(min_length=1, max_length=2_000)
    compliance_id: str = Field(min_length=1, max_length=128)


class Wcag22CheckReport(BaseModel):
    """Aggregate WCAG 2.2 deterministic-check result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = COMPLIANCE_SCHEMA_VERSION

    schema_version: str = Field(default=COMPLIANCE_SCHEMA_VERSION)
    signals_seen: bool = False
    issues: tuple[Wcag22Issue, ...] = Field(default_factory=tuple, max_length=500)


__all__ = [
    "COMPLIANCE_SCHEMA_VERSION",
    "CcpaCategory",
    "CcpaCheckReport",
    "CcpaIssue",
    "CcpaPageSignal",
    "GdprBannerSignal",
    "GdprCategory",
    "GdprCheckReport",
    "GdprCookie",
    "GdprIssue",
    "GdprPageSignals",
    "Soc2Category",
    "Soc2CheckReport",
    "Soc2GateResult",
    "Soc2Issue",
    "Wcag22CheckReport",
    "Wcag22Issue",
    "Wcag22SignalCategory",
]
