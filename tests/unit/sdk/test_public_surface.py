"""The public SDK surface is locked (ADR-0021)."""

from __future__ import annotations

import sentinelqa
import sentinelqa.agent as sdk_agent
import sentinelqa.errors as sdk_errors

# Pinned list — every name listed here MUST be importable as
# `from sentinelqa import <name>`. Drift fails this test; if you remove
# or rename a symbol, update __deprecation_policy.md and the snapshot.
EXPECTED_ROOT = {
    "Sentinel",
    "AuditResult",
    "Finding",
    "Evidence",
    "ModuleResult",
    "RepairSuggestion",
    "TestPlan",
    "Flow",
    "RiskMap",
    "QualityGate",
    "Policy",
    "SentinelError",
    "ConfigError",
    "UnsafeTargetError",
    "DependencyMissingError",
    "TestExecutionError",
    "QualityGateFailedError",
    "RUN_SCHEMA_VERSION",
    "FINDINGS_SCHEMA_VERSION",
    "SCORE_SCHEMA_VERSION",
    "REPAIR_SUGGESTION_SCHEMA_VERSION",
    "AGENT_MESSAGE_SCHEMA_VERSION",
}


def test_public_surface_matches_expected() -> None:
    assert set(sentinelqa.__all__) == EXPECTED_ROOT


def test_every_public_name_is_importable() -> None:
    for name in EXPECTED_ROOT:
        assert hasattr(sentinelqa, name), f"sentinelqa missing public name: {name}"


def test_prd_14_3_class_names_all_present() -> None:
    # PRD §14.3 enumerates the SDK class list verbatim.
    prd_classes = {
        "Sentinel",
        "AuditResult",
        "Finding",
        "Evidence",
        "TestPlan",
        "Flow",
        "RiskMap",
        "QualityGate",
        "Policy",
        "ModuleResult",
        "RepairSuggestion",
    }
    assert prd_classes <= set(sentinelqa.__all__)


def test_errors_submodule_surface() -> None:
    expected = {
        "SentinelError",
        "ConfigError",
        "ConfigFileNotFoundError",
        "ConfigSchemaError",
        "ConfigSecretInlineError",
        "UnsafeTargetError",
        "UnknownHostError",
        "DestructiveWithoutProofError",
        "ForbiddenFlagError",
        "DependencyMissingError",
        "TestExecutionError",
        "QualityGateFailedError",
        "from_dict",
    }
    assert set(sdk_errors.__all__) == expected
    for name in expected:
        assert hasattr(sdk_errors, name), f"sentinelqa.errors missing: {name}"


def test_agent_submodule_surface() -> None:
    expected = {
        "Format",
        "AGENT_MESSAGE_SCHEMA_VERSION",
        "audit_result_to_agent_messages",
        "finding_to_agent_message",
        "format",
        "repair_suggestion_to_agent_message",
    }
    assert set(sdk_agent.__all__) >= expected


def test_no_internal_modules_in_public_surface() -> None:
    # _internal/, _facade, _models, _agent_messages, _errors must NOT be
    # importable through the public root.
    for name in sentinelqa.__all__:
        assert not name.startswith("_"), f"private name in __all__: {name}"


def test_version_accessor_returns_string() -> None:
    assert isinstance(sentinelqa.__version__, str)
    assert sentinelqa.__version__
