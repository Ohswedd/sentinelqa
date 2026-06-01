"""Wire types for :class:`ChaosModule` (, the documentation).

The chaos module is Playwright-driven: TS chaos helpers inject network
slowdowns, expired sessions, duplicate-submit races, etc., into a
target flow and emit per-observation :class:`ChaosEvent` records via
the standard JSONL bridge. The Python side ingests those
events, persists ``chaos/<category>.json`` per scenario category, and
translates "bad" observations into the documentation :class:`Finding`s.

No event shape carries an exploit payload or evasion knob — the module
records *what the UI did under the chaos scenario* (e.g. "no error
state shown"), never *how to bypass the scenario's safety mitigations*.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CHAOS_RESULT_SCHEMA_VERSION = "1"
"""Stable wire version of ``chaos/<category>.json`` artifacts."""

ChaosCategory = Literal["network", "session", "ux", "data"]
"""Top-level chaos scenario category (the documentation grouping)."""

ChaosObservation = Literal[
    # Network / data: app raised JS error or surfaced no error state.
    "uncaught_error",
    "no_error_state",
    # Session: bad UX on expired token / missing permissions.
    "no_redirect_on_expired_session",
    "no_graceful_permission_denial",
    # UX edge cases.
    "duplicate_submit_accepted",
    "lost_form_state_on_navigation",
    "white_screen_on_refresh",
    # Data scenarios.
    "missing_empty_state",
    "dom_explosion_on_large_dataset",
    "crash_on_corrupted_storage",
    # Positive outcomes (recorded for completeness; never raise a finding).
    "handled_gracefully",
]
"""Each chaos event resolves to exactly one observation.

The orchestrator maps non-``handled_gracefully`` observations to
findings via :func:`modules.chaos.findings.findings_from_results`.
"""


class ChaosEvent(BaseModel):
    """One observation emitted while a chaos scenario was active.

    The TS chaos helpers (``packages/ts-runtime/src/chaos/*``) emit these
    as JSONL lines into ``<run-dir>/chaos/events.jsonl``. The Python
    ingestion layer parses them into :class:`ChaosScenarioResult`
    objects, never trusting the file's contents past the Pydantic
    validators below.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(min_length=1, max_length=128)
    """Stable scenario identifier (e.g. ``network.api_500``)."""
    category: ChaosCategory
    flow: str = Field(min_length=1, max_length=128)
    """Name of the user flow exercised under the chaos scenario."""
    observation: ChaosObservation
    route: str | None = Field(default=None, max_length=2048)
    detail: str = Field(default="", max_length=2000)
    evidence: dict[str, str] = Field(default_factory=dict)

    @property
    def is_bad(self) -> bool:
        """True if this observation should become a :class:`Finding`."""

        return self.observation != "handled_gracefully"


class ChaosScenarioResult(BaseModel):
    """Roll-up of one scenario / flow combination.

    The ingestion layer aggregates events by ``(scenario_id, flow)`` so
    each artifact row represents one execution of one scenario against
    one flow — exactly the granularity findings need.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = CHAOS_RESULT_SCHEMA_VERSION
    scenario_id: str = Field(min_length=1, max_length=128)
    category: ChaosCategory
    flow: str = Field(min_length=1, max_length=128)
    events: tuple[ChaosEvent, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(ge=0, default=0)
    skipped: bool = False
    skip_reason: str | None = Field(default=None, max_length=512)

    @property
    def bad_events(self) -> tuple[ChaosEvent, ...]:
        """Events that should raise findings."""

        return tuple(event for event in self.events if event.is_bad)


class ChaosCategoryReport(BaseModel):
    """Aggregate of every scenario result in one category.

    Persisted as ``chaos/<category>.json``. The category-level layer
    keeps the per-category artifact small enough for humans to skim
    while the run-level ``chaos/index.json`` covers the full sweep.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = CHAOS_RESULT_SCHEMA_VERSION
    category: ChaosCategory
    results: tuple[ChaosScenarioResult, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(ge=0, default=0)
    skipped: bool = False
    skip_reason: str | None = Field(default=None, max_length=512)


class ChaosRunOutcome(BaseModel):
    """Top-level aggregate persisted as ``chaos/index.json``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = CHAOS_RESULT_SCHEMA_VERSION
    categories: tuple[ChaosCategoryReport, ...] = Field(default_factory=tuple)
    duration_ms: int = Field(ge=0)
    incomplete: bool = False
    events_path: str | None = Field(default=None, max_length=512)
    """Relative path to the raw JSONL event log, if persisted."""


__all__ = [
    "CHAOS_RESULT_SCHEMA_VERSION",
    "ChaosCategory",
    "ChaosCategoryReport",
    "ChaosEvent",
    "ChaosObservation",
    "ChaosRunOutcome",
    "ChaosScenarioResult",
]
