"""Typed accessibility result models (, ADR-0016).

The accessibility module is the first SentinelQA module that does NOT
drive a Playwright spec set through 's runner — instead it
invokes ``sentinel-ts audit-a11y`` to load each route, inject axe-core,
and run keyboard / landmark / accessible-name checks per route. The
TS subcommand returns one ``A11yPageResult`` per route which the Python
side translates into typed :class:`engine.domain.finding.Finding` records
via :mod:`modules.accessibility.findings`.

These wire models are intentionally separated from the runner ABI in
:mod:`engine.runner.results` because:

- They carry per-rule axe metadata (impact, help URL, target selectors).
- The check set is per-route, not per-test — there is no
 ``TestExecution`` analogue.
- The audit runs as a single TS process for the whole module, not one
 process per spec, so the partial-stream tolerance and quarantine
 semantics from don't apply.

Schema version is locked under ADR-0016 §3.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

A11Y_RESULT_SCHEMA_VERSION = "1"
"""Wire format of the ``a11y/<route-slug>.json`` envelope."""

AxeImpact = Literal["critical", "serious", "moderate", "minor"]
KeyboardCategory = Literal["keyboard-navigation", "focus-trap", "focus-visible"]
LandmarkCategory = Literal["missing-landmark", "duplicate-landmark"]
Wcag22Category = Literal[
    "focus-obscured",
    "target-size-min",
    "dragging-movements",
    "redundant-entry",
    "accessible-authentication",
]
"""WCAG 2.2 success-criteria covered by deterministic Phase 34 checks.

These are the SCs axe-core 4.10 either does not cover, covers only
behind an experimental flag, or covers without enough page-shape
context to be reliable. The deterministic check functions live in
:mod:`modules.accessibility.checks.wcag22`.
"""


class AxeNode(BaseModel):
    """One DOM node implicated by an axe violation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    html: str = Field(default="", max_length=4_000)
    failure_summary: str = Field(default="", max_length=2_000)


class AxeViolation(BaseModel):
    """One axe-core violation (one rule, one or more nodes)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(min_length=1, max_length=128)
    impact: AxeImpact
    help: str = Field(default="", max_length=4_000)
    help_url: str = Field(default="", max_length=2_048)
    description: str = Field(default="", max_length=4_000)
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    nodes: tuple[AxeNode, ...] = Field(default_factory=tuple, max_length=200)
    experimental: bool = False


class KeyboardIssue(BaseModel):
    """One keyboard navigation issue (skipped element, trap, focus-visible)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: KeyboardCategory
    selector: str = Field(default="", max_length=2_048)
    description: str = Field(min_length=1, max_length=2_000)


class LandmarkIssue(BaseModel):
    """A missing or duplicate landmark region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: LandmarkCategory
    landmark: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2_000)


class AccessibleNameIssue(BaseModel):
    """An interactive element missing a computable accessible name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selector: str = Field(min_length=1, max_length=2_048)
    role: str = Field(default="", max_length=64)
    description: str = Field(min_length=1, max_length=2_000)


class Wcag22Issue(BaseModel):
    """One WCAG 2.2 deterministic check issue ( / ADR-0046).

    Categories map 1:1 to a WCAG 2.2 success criterion via
    ``success_criterion`` (e.g. ``2.5.8`` for *Target Size (Minimum)*).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Wcag22Category
    success_criterion: str = Field(min_length=1, max_length=16)
    selector: str = Field(default="", max_length=2_048)
    description: str = Field(min_length=1, max_length=2_000)


class A11yPageResult(BaseModel):
    """Aggregate accessibility result for one route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = A11Y_RESULT_SCHEMA_VERSION

    route: str = Field(min_length=1, max_length=2_048)
    url: str = Field(min_length=1, max_length=2_048)
    fetched_at: str = Field(min_length=1, max_length=64)
    axe_violations: tuple[AxeViolation, ...] = Field(default_factory=tuple, max_length=500)
    keyboard_issues: tuple[KeyboardIssue, ...] = Field(default_factory=tuple, max_length=500)
    landmark_issues: tuple[LandmarkIssue, ...] = Field(default_factory=tuple, max_length=200)
    accessible_name_issues: tuple[AccessibleNameIssue, ...] = Field(
        default_factory=tuple, max_length=500
    )
    wcag22_issues: tuple[Wcag22Issue, ...] = Field(default_factory=tuple, max_length=500)
    duration_ms: int = Field(ge=0)
    schema_version: str = Field(default=A11Y_RESULT_SCHEMA_VERSION)
    error: str | None = Field(default=None, max_length=2_000)


class A11yRunOutcome(BaseModel):
    """Aggregate output of running the accessibility module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pages: tuple[A11yPageResult, ...] = Field(default_factory=tuple, max_length=500)
    incomplete: bool = False
    duration_ms: int = Field(ge=0)

    @property
    def total_issues(self) -> int:
        return sum(
            len(p.axe_violations)
            + len(p.keyboard_issues)
            + len(p.landmark_issues)
            + len(p.accessible_name_issues)
            + len(p.wcag22_issues)
            for p in self.pages
        )


__all__ = [
    "A11Y_RESULT_SCHEMA_VERSION",
    "A11yPageResult",
    "A11yRunOutcome",
    "AccessibleNameIssue",
    "AxeImpact",
    "AxeNode",
    "AxeViolation",
    "KeyboardCategory",
    "KeyboardIssue",
    "LandmarkCategory",
    "LandmarkIssue",
    "Wcag22Category",
    "Wcag22Issue",
]
