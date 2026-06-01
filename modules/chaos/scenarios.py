"""Canonical chaos scenario catalog (, the documentation).

Each :class:`ChaosScenario` is a *named, bounded* injection the TS
chaos helpers know how to perform via Playwright's ``route()`` API
(network/data scenarios) or its session / navigation primitives
(session/ux scenarios). The catalog is the single source of truth
both runtimes consult: the Python module uses it to validate
incoming options, and the TS helpers use the same identifiers in
their event ``scenario_id`` fields so the two sides stay in lockstep
across language boundaries.

The catalog deliberately mirrors the documentation's flat scenario list (and
nothing more). New scenarios must be added here first; our engineering rules
forbids drive-by chaos additions without explicit PRD updates.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from modules.chaos.models import ChaosCategory, ChaosObservation


class ChaosScenario(BaseModel):
    """Static catalog entry describing one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128)
    category: ChaosCategory
    summary: str = Field(min_length=1, max_length=300)
    bad_observations: tuple[ChaosObservation, ...] = Field(min_length=1)
    """Observations that, if emitted by this scenario, mean the UI failed."""


# Network: route-level injections (`page.route(...)`).
_NETWORK: Final[tuple[ChaosScenario, ...]] = (
    ChaosScenario(
        id="network.slow_3g",
        category="network",
        summary="Throttle every response to ~400 Kbps with 400 ms RTT.",
        bad_observations=("uncaught_error",),
    ),
    ChaosScenario(
        id="network.offline",
        category="network",
        summary="Block every outgoing request with a network failure.",
        bad_observations=("uncaught_error", "no_error_state"),
    ),
    ChaosScenario(
        id="network.api_500",
        category="network",
        summary="Return HTTP 500 for matched API URLs.",
        bad_observations=("uncaught_error", "no_error_state"),
    ),
    ChaosScenario(
        id="network.api_timeout",
        category="network",
        summary="Stall matched API URLs, then abort after 30 s.",
        bad_observations=("uncaught_error", "no_error_state"),
    ),
)


# Session: token / claim injections via ``Authorization`` header rewriting.
_SESSION: Final[tuple[ChaosScenario, ...]] = (
    ChaosScenario(
        id="session.expired_token",
        category="session",
        summary=(
            "Send Authorization: Bearer expired.token.here and observe whether "
            "the UI redirects to login."
        ),
        bad_observations=("no_redirect_on_expired_session", "uncaught_error"),
    ),
    ChaosScenario(
        id="session.missing_permissions",
        category="session",
        summary=(
            "Strip permission claims from a sandbox JWT and verify the UI "
            "denies access gracefully."
        ),
        bad_observations=("no_graceful_permission_denial", "uncaught_error"),
    ),
)


# UX: form / navigation edge cases.
_UX: Final[tuple[ChaosScenario, ...]] = (
    ChaosScenario(
        id="ux.duplicate_submit",
        category="ux",
        summary="Click the primary submit button twice in rapid succession.",
        bad_observations=("duplicate_submit_accepted",),
    ),
    ChaosScenario(
        id="ux.double_click_race",
        category="ux",
        summary="Fire a double-click race on the same primary action.",
        bad_observations=("duplicate_submit_accepted",),
    ),
    ChaosScenario(
        id="ux.back_forward",
        category="ux",
        summary="Drive browser back/forward across multi-step forms.",
        bad_observations=("lost_form_state_on_navigation",),
    ),
    ChaosScenario(
        id="ux.refresh_mid_flow",
        category="ux",
        summary="Refresh the page mid-flow (e.g. during payment / form submit).",
        bad_observations=("white_screen_on_refresh", "lost_form_state_on_navigation"),
    ),
)


# Data: dataset shape + storage corruption.
_DATA: Final[tuple[ChaosScenario, ...]] = (
    ChaosScenario(
        id="data.empty_dataset",
        category="data",
        summary="Mock the list API to return an empty array.",
        bad_observations=("missing_empty_state",),
    ),
    ChaosScenario(
        id="data.large_dataset",
        category="data",
        summary="Mock the list API to return ~1000 items; expect pagination or virtualization.",
        bad_observations=("dom_explosion_on_large_dataset",),
    ),
    ChaosScenario(
        id="data.storage_corruption",
        category="data",
        summary="Write garbage into localStorage for known keys; expect graceful fallback.",
        bad_observations=("crash_on_corrupted_storage",),
    ),
)


CATALOG: Final[tuple[ChaosScenario, ...]] = (*_NETWORK, *_SESSION, *_UX, *_DATA)
"""Every scenario known to the chaos module, in canonical order."""

CATALOG_BY_ID: Final[dict[str, ChaosScenario]] = {s.id: s for s in CATALOG}

DEFAULT_CATEGORIES: Final[tuple[ChaosCategory, ...]] = (
    "network",
    "session",
    "ux",
    "data",
)
"""Categories the CLI runs by default when none is named."""


def scenarios_for_category(category: ChaosCategory) -> tuple[ChaosScenario, ...]:
    """Return every catalog entry in the given category."""

    return tuple(s for s in CATALOG if s.category == category)


def is_known_scenario(scenario_id: str) -> bool:
    """Return True if ``scenario_id`` is in the canonical catalog."""

    return scenario_id in CATALOG_BY_ID


__all__ = [
    "CATALOG",
    "CATALOG_BY_ID",
    "DEFAULT_CATEGORIES",
    "ChaosScenario",
    "is_known_scenario",
    "scenarios_for_category",
]
