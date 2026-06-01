"""Typed signal models the LLM-Code audit module consumes.

The module deliberately does NOT spawn a parallel Playwright session.
Every check operates on already-captured signals (Phase 05 discovery
output, optional runner-collected runtime evidence, optional source
root scan). Tests construct these models directly; production wiring
reads what is available from the run directory and skips checks whose
signals are missing (our engineering rules: no fake completion).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# DOM / interactive elements
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ButtonObservation:
    """One interactive button observed during discovery or runtime."""

    route_url: str
    selector: str
    label: str
    disabled: bool = False
    # Static signals (from DOM): has any of `onclick`, `onsubmit`,
    # `formaction`, `data-action`, or an enclosing `<form action>`.
    has_static_handler: bool = False
    # Runtime signals (from runner). When the runner is not available
    # they default to ``None`` so the check can distinguish "did not
    # observe activity" from "observed no activity".
    observed_network_within_2s: bool | None = None
    observed_navigation: bool | None = None
    observed_console_error: bool | None = None
    observed_dom_change: bool | None = None
    # Heuristic exclusions — buttons inside <details>, carousel
    # indicators, accordion toggles. The check skips these.
    is_decorative: bool = False
    is_disclosure: bool = False


# ---------------------------------------------------------------------------
# Routes / endpoints (Phase 05 cross-reference signal sources)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkReference:
    """An internal link the frontend renders or routes to."""

    source_route: str
    target_path: str
    source: str = "anchor"  # 'anchor' | 'router_push' | 'link_component'


@dataclass(frozen=True)
class ApiReference:
    """An API endpoint the frontend references in code."""

    path: str
    method: str = "GET"
    source_file: str | None = None


# ---------------------------------------------------------------------------
# Mock-data and placeholder-text signals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleSnippet:
    """A JS bundle or source file the scanner can grep."""

    path: str
    body: str


@dataclass(frozen=True)
class RenderedTextSample:
    """Plain text rendered on a specific route."""

    route_url: str
    text: str
    is_authenticated_flow: bool = False
    priority: str = "p3"  # 'p0' | 'p1' | 'p2' | 'p3'
    selector: str | None = None


# ---------------------------------------------------------------------------
# Forms inventory (Phase 05 forms.json compatible shape)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormSignal:
    """One form pulled from forms.json + its exercise result."""

    form_id: str
    route_url: str
    action_url: str | None
    method: str
    submit_handler_present: bool
    was_exercised: bool = False
    produced_network_request: bool | None = None


# ---------------------------------------------------------------------------
# CRUD / resource detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceCrudSignal:
    """REST coverage for a single resource."""

    resource: str
    has_create: bool = False
    has_read: bool = False
    has_update: bool = False
    has_delete: bool = False
    # UI affordances seen on a list page for this resource.
    ui_has_create_button: bool = False
    ui_has_edit_button: bool = False
    ui_has_delete_button: bool = False
    sample_endpoint: str | None = None


# ---------------------------------------------------------------------------
# Auth boundary probe — UI-only auth check (HTTP probe)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthRouteProbe:
    """One route the UI hides from the low-priv user.

    ``backend_status_code`` is populated by the HTTP probe; the check
    flags a finding when the backend serves a 2xx for a route the UI
    refused to render.
    """

    route_path: str
    method: str = "GET"
    role: str = "anonymous"
    ui_visible: bool = False
    backend_status_code: int | None = None


# ---------------------------------------------------------------------------
# Hardcoded credentials
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """One source / bundle file to scan for hardcoded credentials."""

    path: str
    body: str


# ---------------------------------------------------------------------------
# Browser storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrowserStorageSample:
    """A dump of localStorage / sessionStorage for one route."""

    route_url: str
    store: str  # 'localStorage' | 'sessionStorage'
    entries: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loading / error UI signal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadingErrorObservation:
    """A scripted probe that delayed / failed a target API call."""

    route_url: str
    probed_endpoint: str
    delay_ms: int
    forced_status: int | None
    # Observed within a 2 s window.
    showed_loading_indicator: bool
    showed_error_state: bool
    ui_reported_success: bool


# ---------------------------------------------------------------------------
# Validation mismatch probe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationProbe:
    """One frontend / backend validation comparison."""

    form_id: str
    route_url: str
    endpoint_path: str
    field: str
    payload_kind: str  # 'missing' | 'too_long' | 'wrong_type'
    frontend_would_submit: bool
    backend_status_code: int


# ---------------------------------------------------------------------------
# Console errors / unhandled promises
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsoleEntry:
    """One console message captured during runner execution."""

    route_url: str
    level: str  # 'error' | 'warn' | 'log' | 'info' | 'debug'
    text: str
    source_url: str | None = None
    is_unhandled_rejection: bool = False
    ui_reported_success: bool = False


# ---------------------------------------------------------------------------
# Module-level container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LlmAuditInputs:
    """Everything the LLM-audit module needs in one struct.

    Production wiring populates whatever it can find under the run
    directory; tests build the struct directly. Every field defaults to
    an empty tuple / mapping so a missing signal simply skips the
    relevant checks.
    """

    buttons: tuple[ButtonObservation, ...] = field(default_factory=tuple)
    link_references: tuple[LinkReference, ...] = field(default_factory=tuple)
    api_references: tuple[ApiReference, ...] = field(default_factory=tuple)
    observed_routes: tuple[str, ...] = field(default_factory=tuple)
    observed_route_status: Mapping[str, int] = field(default_factory=dict)
    observed_endpoints: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    openapi_endpoints: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    bundles: tuple[BundleSnippet, ...] = field(default_factory=tuple)
    rendered_text: tuple[RenderedTextSample, ...] = field(default_factory=tuple)
    forms: tuple[FormSignal, ...] = field(default_factory=tuple)
    resources: tuple[ResourceCrudSignal, ...] = field(default_factory=tuple)
    auth_route_probes: tuple[AuthRouteProbe, ...] = field(default_factory=tuple)
    source_files: tuple[SourceFile, ...] = field(default_factory=tuple)
    storage_samples: tuple[BrowserStorageSample, ...] = field(default_factory=tuple)
    loading_error_observations: tuple[LoadingErrorObservation, ...] = field(
        default_factory=tuple,
    )
    validation_probes: tuple[ValidationProbe, ...] = field(default_factory=tuple)
    console_entries: tuple[ConsoleEntry, ...] = field(default_factory=tuple)
    third_party_console_hosts: tuple[str, ...] = field(default_factory=tuple)
    discovery_path: Path | None = None


__all__ = [
    "ButtonObservation",
    "LinkReference",
    "ApiReference",
    "BundleSnippet",
    "RenderedTextSample",
    "FormSignal",
    "ResourceCrudSignal",
    "AuthRouteProbe",
    "SourceFile",
    "BrowserStorageSample",
    "LoadingErrorObservation",
    "ValidationProbe",
    "ConsoleEntry",
    "LlmAuditInputs",
]
