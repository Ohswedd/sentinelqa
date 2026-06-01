"""Phase 24 task 24.01 — plugin Protocol surface (our product spec2).

These tests pin the shape of :mod:`sentinelqa.plugins` so external
plugin authors get a stable contract. Anything they re-export here is
gated by ``sentinelqa.plugins.__all__`` and (per task 24.05) by
:data:`PROTOCOL_VERSION`.
"""

from __future__ import annotations

import re
from typing import Any, Protocol, get_type_hints

import pytest

import sentinelqa.plugins as plugins_mod
from sentinelqa.plugins import (
    ENTRY_POINT_GROUP,
    PLUGIN_PROTOCOLS,
    PROTOCOL_VERSION,
    AuthPlugin,
    CloudExecutionPlugin,
    DataFixturePlugin,
    DiscoveryPlugin,
    PluginContext,
    PolicyPlugin,
    ReporterPlugin,
    RunnerPlugin,
    ScannerPlugin,
)

PLUGIN_KINDS = (
    DiscoveryPlugin,
    ScannerPlugin,
    RunnerPlugin,
    ReporterPlugin,
    PolicyPlugin,
    AuthPlugin,
    DataFixturePlugin,
    CloudExecutionPlugin,
)


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------


def test_protocol_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", PROTOCOL_VERSION), PROTOCOL_VERSION


def test_entry_point_group_is_stable() -> None:
    # The group name is part of the plugin packaging contract — changing
    # it would break every installed plugin. Task 24.05 ADR-protects it.
    assert ENTRY_POINT_GROUP == "sentinelqa.plugins"


def test_all_exports_are_real_attributes() -> None:
    for name in plugins_mod.__all__:
        assert hasattr(plugins_mod, name), name


def test_plugin_protocols_registry_covers_every_kind() -> None:
    registered = set(PLUGIN_PROTOCOLS.values())
    assert registered == set(PLUGIN_KINDS)


def test_plugin_protocols_keys_match_kind_attribute() -> None:
    for kind_str, protocol_cls in PLUGIN_PROTOCOLS.items():
        assert getattr(protocol_cls, "kind") == kind_str  # noqa: B009


# ---------------------------------------------------------------------------
# Shape of every plugin Protocol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("protocol_cls", PLUGIN_KINDS)
def test_each_plugin_is_a_runtime_checkable_protocol(protocol_cls: type) -> None:
    # The loader uses isinstance() to verify the plugin implements its
    # declared kind; runtime_checkable is therefore mandatory.
    assert issubclass(protocol_cls, Protocol)  # type: ignore[arg-type]
    # runtime_checkable sets this private marker (CPython detail but
    # exercised across our supported interpreters).
    assert getattr(protocol_cls, "_is_runtime_protocol", False) is True


@pytest.mark.parametrize("protocol_cls", PLUGIN_KINDS)
def test_each_plugin_declares_kind_str(protocol_cls: type) -> None:
    kind = getattr(protocol_cls, "kind", None)
    assert isinstance(kind, str) and kind, protocol_cls.__name__
    # Kind strings are stable identifiers used in manifests and logs.
    assert re.fullmatch(r"[a-z_]+", kind), kind


@pytest.mark.parametrize("protocol_cls", PLUGIN_KINDS)
def test_each_plugin_requires_four_common_attributes(protocol_cls: type) -> None:
    # The four attributes every plugin must declare per our product spec2.
    hints = get_type_hints(protocol_cls)
    for required in ("name", "version", "capabilities", "permissions"):
        assert required in hints, f"{protocol_cls.__name__} missing {required}"


# ---------------------------------------------------------------------------
# Method shapes per kind
# ---------------------------------------------------------------------------


def _has_method(cls: type, method: str) -> bool:
    attr = getattr(cls, method, None)
    return callable(attr)


def test_scanner_plugin_has_run_method_returning_module_result() -> None:
    assert _has_method(ScannerPlugin, "run")
    hints = get_type_hints(ScannerPlugin.run)
    # The PRD pins ScannerPlugin.run(ctx) -> ModuleResult.
    assert "context" in hints
    assert hints["return"].__name__ == "ModuleResult"


def test_discovery_plugin_has_discover_method() -> None:
    assert _has_method(DiscoveryPlugin, "discover")


def test_runner_plugin_has_run_method() -> None:
    assert _has_method(RunnerPlugin, "run")


def test_reporter_plugin_has_emit_method_and_formats() -> None:
    assert _has_method(ReporterPlugin, "emit")
    # Reporters MUST declare the format names they handle.
    hints = get_type_hints(ReporterPlugin)
    assert "formats" in hints


def test_policy_plugin_has_evaluate_method() -> None:
    assert _has_method(PolicyPlugin, "evaluate")


def test_auth_plugin_has_acquire_method() -> None:
    assert _has_method(AuthPlugin, "acquire")


def test_data_fixture_plugin_has_setup_and_teardown() -> None:
    assert _has_method(DataFixturePlugin, "setup")
    assert _has_method(DataFixturePlugin, "teardown")


def test_cloud_execution_plugin_has_submit_method() -> None:
    assert _has_method(CloudExecutionPlugin, "submit")


# ---------------------------------------------------------------------------
# PluginContext shape
# ---------------------------------------------------------------------------


def test_plugin_context_is_runtime_checkable_protocol() -> None:
    assert issubclass(PluginContext, Protocol)  # type: ignore[arg-type]
    assert getattr(PluginContext, "_is_runtime_protocol", False) is True


def test_plugin_context_attributes() -> None:
    hints = get_type_hints(PluginContext)
    for required in (
        "run_id",
        "target_url",
        "run_dir",
        "config_snapshot",
        "granted_permissions",
    ):
        assert required in hints, required


def test_plugin_context_has_permission_check_and_artifact_path() -> None:
    assert _has_method(PluginContext, "has_permission")
    assert _has_method(PluginContext, "artifact_path")


# ---------------------------------------------------------------------------
# Acceptance criterion (24.01): a concrete class implementing
# ScannerPlugin passes isinstance(...) so the loader can identify it.
# ---------------------------------------------------------------------------


def test_concrete_scanner_implements_protocol() -> None:
    from engine.domain.ids import IdGenerator
    from engine.domain.module_result import ModuleResult

    class TinyScanner:
        kind = "scanner"
        name = "tiny"
        version = "0.1.0"
        capabilities = frozenset({"audit"})
        permissions = frozenset({"fs.read"})

        def run(self, context: Any) -> ModuleResult:
            ids = IdGenerator()
            return ModuleResult(
                id=ids.new("MOD"),
                name="tiny",
                status="passed",
                findings=(),
                metrics={},
                duration_ms=0,
                errors=(),
            )

    instance = TinyScanner()
    assert isinstance(instance, ScannerPlugin)


def test_class_missing_required_attribute_is_not_a_scanner() -> None:
    class MissingAttrs:
        name = "broken"
        # missing version / capabilities / permissions

        def run(self, context: Any) -> Any:
            return None

    assert not isinstance(MissingAttrs(), ScannerPlugin)


def test_class_missing_run_method_is_not_a_scanner() -> None:
    class NoRun:
        kind = "scanner"
        name = "no-run"
        version = "0.1.0"
        capabilities: frozenset[str] = frozenset()
        permissions: frozenset[str] = frozenset()

    assert not isinstance(NoRun(), ScannerPlugin)


def test_reporter_concrete_implementation_matches_protocol() -> None:
    class TinyReporter:
        kind = "reporter"
        name = "tiny"
        version = "0.1.0"
        capabilities = frozenset({"report"})
        permissions = frozenset({"fs.write:.sentinel/runs"})
        formats: tuple[str, ...] = ("csv",)

        def emit(self, result: Any, context: Any) -> dict[str, Any]:
            return {}

    assert isinstance(TinyReporter(), ReporterPlugin)
