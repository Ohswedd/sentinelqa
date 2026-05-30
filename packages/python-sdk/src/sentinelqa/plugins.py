"""Public plugin contracts (PRD §22, CLAUDE §22).

This is the SDK-public surface third-party plugins implement. Each
Protocol pins:

- A short ``kind`` string (``"scanner"``, ``"reporter"``, ...).
- The four class-level attributes every plugin must declare:
  ``name``, ``version``, ``capabilities``, ``permissions``.
- One or more typed methods specific to the plugin kind.

The Protocols are intentionally minimal. A plugin author depends on
:mod:`sentinelqa.plugins` and the SDK's public domain models
(``Finding``, ``ModuleResult``, etc.) — never on :mod:`engine.*`. The
loader in :mod:`engine.plugins` (Phase 24 task 24.02) does the actual
entry-point discovery, manifest validation, semver compatibility check,
and ``PluginContext`` wiring.

The ``PluginContext`` Protocol describes the runtime surface a loaded
plugin sees; the actual implementation lives in :mod:`engine.plugins`
and only exposes APIs the plugin's manifest declared (task 24.03).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from engine.domain.module_result import ModuleResult

from sentinelqa._models import AuditResult

# ---------------------------------------------------------------------------
# Versioning (Phase 24 task 24.05)
# ---------------------------------------------------------------------------

#: Semantic version of the plugin protocol surface. Plugins declare a
#: ``requires_protocol`` semver range against this. Bumping the major
#: requires an ADR (CLAUDE §22, §40).
PROTOCOL_VERSION: str = "1.0.0"


# ---------------------------------------------------------------------------
# Runtime context (Phase 24 task 24.03)
# ---------------------------------------------------------------------------


@runtime_checkable
class PluginContext(Protocol):
    """Runtime surface a loaded plugin receives.

    The orchestrator hands every plugin call a :class:`PluginContext`.
    The context exposes ONLY the APIs the plugin's manifest declared
    via ``permissions``; reaching for anything else raises
    :class:`PluginPermissionError` (defined in :mod:`engine.plugins`).

    Plugin authors program against this Protocol; the engine ships the
    concrete implementation.
    """

    #: Stable run identifier (matches ``run.json#/run_id``).
    run_id: str
    #: Target URL the audit is running against (already safety-checked).
    target_url: str
    #: Per-run artifact directory (PRD §11, CLAUDE §11).
    run_dir: Path
    #: Read-only snapshot of the loaded SentinelQA config (PRD §17).
    config_snapshot: Mapping[str, Any]
    #: The permissions the loader granted to this plugin (frozen).
    granted_permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        """Return True if ``permission`` is in the granted set."""

    def artifact_path(self, name: str) -> Path:
        """Return a writable path under the run's plugin artifact dir.

        Requires ``fs.write:.sentinel/runs`` in the manifest.
        """


# ---------------------------------------------------------------------------
# Per-kind Protocols
# ---------------------------------------------------------------------------


class _PluginBase(Protocol):
    """Common attribute surface every plugin Protocol shares."""

    #: Distinguishes the plugin kind across error / log surfaces.
    kind: ClassVar[str]
    #: Stable plugin name (lowercase, kebab-case).
    name: str
    #: Plugin's own semver string (independent of :data:`PROTOCOL_VERSION`).
    version: str
    #: Declared capabilities. Forbidden capabilities (CLAUDE §6,
    #: ``engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES``)
    #: are rejected at load time.
    capabilities: frozenset[str]
    #: Declared runtime permissions (e.g. ``"network.outbound"``,
    #: ``"fs.read"``, ``"fs.write:.sentinel/runs"``,
    #: ``"subprocess.spawn"``). The loader enforces these at runtime.
    permissions: frozenset[str]


@runtime_checkable
class DiscoveryPlugin(_PluginBase, Protocol):
    """Custom discovery backend (PRD §22.1 "Discovery plugin").

    Returns a dict shaped like ``discovery.json``; downstream modules
    consume it identically to the built-in HTTP/Playwright backends.
    """

    kind: ClassVar[str] = "discovery"

    def discover(self, context: PluginContext) -> Mapping[str, Any]:
        """Crawl the target and return a discovery payload."""


@runtime_checkable
class ScannerPlugin(_PluginBase, Protocol):
    """Custom audit module (PRD §22.1 "Scanner plugin", §22.2).

    Returns a typed :class:`ModuleResult` exactly like a built-in
    module (CLAUDE §9). The orchestrator merges the result into the run
    so scoring, reporting, and policy gating treat it identically.
    """

    kind: ClassVar[str] = "scanner"

    def run(self, context: PluginContext) -> ModuleResult:
        """Execute the scan and return a :class:`ModuleResult`."""


@runtime_checkable
class RunnerPlugin(_PluginBase, Protocol):
    """Custom test-runner backend (PRD §22.1 "Runner plugin").

    Replaces or augments the built-in local/Docker Playwright runners
    (Phase 08). The return value is a free-form mapping that the
    orchestrator hands back to the calling scanner; the SDK does not
    pin a Runner output shape because runners differ widely.
    """

    kind: ClassVar[str] = "runner"

    def run(
        self,
        invocation: Mapping[str, Any],
        context: PluginContext,
    ) -> Mapping[str, Any]:
        """Execute ``invocation`` and return a serialisable outcome."""


@runtime_checkable
class ReporterPlugin(_PluginBase, Protocol):
    """Custom report writer (PRD §22.1 "Reporter plugin").

    The plugin advertises which format names it emits and is invoked
    after scoring + policy decision (CLAUDE §10). Returns a mapping of
    ``{format_name: written_path}`` so the dispatcher can record the
    emitted artifacts on ``run.json``.

    This Protocol is the SDK-public surface; the engine's internal
    :class:`engine.reporter.dispatcher.ReporterPlugin` is a separate
    type used by built-in writers and remains untouched by this phase.
    """

    kind: ClassVar[str] = "reporter"
    #: Format names this reporter handles (e.g. ``("csv",)``).
    formats: tuple[str, ...]

    def emit(
        self,
        result: AuditResult,
        context: PluginContext,
    ) -> Mapping[str, Path]:
        """Write the configured formats and return ``{name: path}``."""


@runtime_checkable
class PolicyPlugin(_PluginBase, Protocol):
    """Custom policy evaluator (PRD §22.1 "Policy plugin").

    Receives the same inputs as the built-in policy gate (Phase 14) and
    returns a release decision. The orchestrator records both the
    built-in decision and any plugin decisions; the strictest verdict
    wins (CLAUDE §25).
    """

    kind: ClassVar[str] = "policy"

    def evaluate(
        self,
        result: AuditResult,
        context: PluginContext,
    ) -> Mapping[str, Any]:
        """Return ``{"decision": "...", "reasons": [...]}``."""


@runtime_checkable
class AuthPlugin(_PluginBase, Protocol):
    """Custom auth-acquisition plugin (PRD §22.1 "Auth plugin").

    Replaces the generated-login fixture for projects with bespoke
    auth flows (SSO, MFA bypass tokens, vendor-specific test
    credentials). MUST NOT log or persist credentials (CLAUDE §33).
    """

    kind: ClassVar[str] = "auth"

    def acquire(
        self,
        target_url: str,
        context: PluginContext,
    ) -> Mapping[str, Any]:
        """Return ``{"cookies": ..., "storage": ..., "headers": ...}``."""


@runtime_checkable
class DataFixturePlugin(_PluginBase, Protocol):
    """Custom data fixture plugin (PRD §22.1 "Data fixture plugin").

    Seeds and tears down per-run test data. Only invoked when
    ``security.mode == authorized_destructive`` and the manifest
    declares the ``data.seed`` capability (CLAUDE §6).
    """

    kind: ClassVar[str] = "data_fixture"

    def setup(self, context: PluginContext) -> Mapping[str, Any]:
        """Seed test data; return any handles needed for teardown."""

    def teardown(
        self,
        handles: Mapping[str, Any],
        context: PluginContext,
    ) -> None:
        """Remove anything ``setup`` created."""


@runtime_checkable
class CloudExecutionPlugin(_PluginBase, Protocol):
    """Custom cloud-execution backend (PRD §22.1 "Cloud execution plugin").

    Submits a runner invocation to a remote service (BrowserStack,
    Sauce Labs, internal Kubernetes job runner) and returns the
    aggregated outcome. The plugin is responsible for streaming
    artifacts back into ``context.run_dir`` so the rest of the
    lifecycle is location-agnostic.
    """

    kind: ClassVar[str] = "cloud_execution"

    def submit(
        self,
        invocation: Mapping[str, Any],
        context: PluginContext,
    ) -> Mapping[str, Any]:
        """Submit ``invocation`` and return the remote outcome."""


# ---------------------------------------------------------------------------
# Lookup table (used by loader + tests)
# ---------------------------------------------------------------------------


#: All plugin Protocols keyed by their ``kind`` string. The loader uses
#: this to pick the right Protocol to ``isinstance``-check against.
PLUGIN_PROTOCOLS: Mapping[str, type] = {
    DiscoveryPlugin.kind: DiscoveryPlugin,
    ScannerPlugin.kind: ScannerPlugin,
    RunnerPlugin.kind: RunnerPlugin,
    ReporterPlugin.kind: ReporterPlugin,
    PolicyPlugin.kind: PolicyPlugin,
    AuthPlugin.kind: AuthPlugin,
    DataFixturePlugin.kind: DataFixturePlugin,
    CloudExecutionPlugin.kind: CloudExecutionPlugin,
}


#: Entry-point group plugins register under (see :mod:`engine.plugins`).
ENTRY_POINT_GROUP: str = "sentinelqa.plugins"


__all__ = [
    "PROTOCOL_VERSION",
    "ENTRY_POINT_GROUP",
    "PluginContext",
    "DiscoveryPlugin",
    "ScannerPlugin",
    "RunnerPlugin",
    "ReporterPlugin",
    "PolicyPlugin",
    "AuthPlugin",
    "DataFixturePlugin",
    "CloudExecutionPlugin",
    "PLUGIN_PROTOCOLS",
]
