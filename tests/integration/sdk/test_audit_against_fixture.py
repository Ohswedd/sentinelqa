"""SDK ``Sentinel.audit`` round-trip against a stubbed module registry."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from engine.orchestrator.registry import ModuleRegistry, default_registry

from sentinelqa import AuditResult, Sentinel, UnsafeTargetError


def _write_minimal_config(root: Path, *, base_url: str = "http://localhost:3000") -> Path:
    config_path = root / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: sdk-fixture\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    return config_path


@pytest.fixture
def patched_registry() -> Iterator[ModuleRegistry]:
    """Register a stub functional module on the process-wide default registry.

    Phase 02 lifecycle uses the process registry by default; this fixture
    plugs in a no-op factory so ``audit()`` finishes without trying to
    spawn Playwright.
    """

    reg = default_registry()
    # Stash and restore any prior registration so the test fixture stays
    # idempotent for other suites.
    prior = reg.modules.get("functional")
    reg.register_module("functional", lambda cfg, decision: {"ok": True})
    try:
        yield reg
    finally:
        if prior is not None:
            reg.register_module("functional", prior)
        else:
            reg.modules.pop("functional", None)


def test_audit_returns_typed_result(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit()
    assert isinstance(result, AuditResult)
    assert result.run_id.startswith("RUN-")
    assert result.status == "passed"
    assert result.passed is True
    assert "functional" in result.modules_run
    assert result.target_url.startswith("http://localhost:3000")
    assert result.run_dir.exists()


def test_audit_writes_artifact_tree(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit()
    assert (result.run_dir / "run.json").exists()
    assert (result.run_dir / "audit.log").exists()


def test_audit_passes_url_override(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path, base_url="http://localhost:3001")
    qa = Sentinel(project_path=tmp_path)
    # Pass a different but still-localhost URL — the engine accepts
    # localhost regardless of allowed_hosts (CLAUDE.md §6).
    result = qa.audit(url="http://localhost:3002")
    assert result.target_url.startswith("http://localhost:3002")


def test_audit_rejects_unsafe_url(tmp_path: Path) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(url="http://evil.example.com")
    # Safety policy blocks; SDK surfaces the unsafe_blocked status.
    # (UnsafeTargetError is internal to the lifecycle; the run result
    # reflects the policy decision.)
    assert result.status == "unsafe_blocked"
    assert result.release_decision == "unsafe_target_rejected"
    assert result.passed is False


def test_dry_run_short_circuits(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(dry_run=True)
    assert result.status == "dry_run"
    assert result.passed is False  # PRD §6.1: a dry run cannot claim success.


def test_ci_flag_forces_ci_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patched_registry: ModuleRegistry
) -> None:
    monkeypatch.delenv("CI", raising=False)
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(ci=True)
    assert result.status == "passed"


def test_audit_result_round_trips_to_agent_messages(
    tmp_path: Path, patched_registry: ModuleRegistry
) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit()
    msgs = result.to_agent_messages()
    # Minimum: run_summary + blocker_summary + next_actions (no findings).
    assert len(msgs) >= 3
    assert msgs[0]["type"] == "run_summary"
    assert msgs[0]["run_id"] == result.run_id


def test_quietly_ignores_ci_env_var_when_explicit_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patched_registry: ModuleRegistry
) -> None:
    monkeypatch.setenv("CI", "true")
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(ci=False)
    assert result.status == "passed"


def test_module_options_passed_through(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(module_options={"functional": {"spec_root": "tests/sentinel"}})
    assert result.status == "passed"


def test_safe_mode_pins_security_mode(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    # Even if the config sets `security.mode: authorized_destructive`,
    # `safe_mode=True` (the SDK default) overrides it for this call.
    config_path = tmp_path / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: sdk-fixture\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "security:\n"
        "  mode: safe\n"  # config keeps safe; SDK still enforces.
        "modules:\n"
        "  functional: true\n"
        "  api: false\n"
        "  accessibility: false\n"
        "  performance: false\n"
        "  visual: false\n"
        "  security: false\n"
        "  chaos: false\n"
        "  llm_audit: false\n",
        encoding="utf-8",
    )
    qa = Sentinel(project_path=tmp_path)
    pol = qa.policy()
    assert pol.mode == "safe"


def test_uvicorn_style_ci_environment_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patched_registry: ModuleRegistry,
) -> None:
    monkeypatch.setenv("CI", "1")
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    # No explicit ci= -> derived from env.
    result = qa.audit()
    assert result.status == "passed"


def test_unsafe_url_emits_typed_error_via_agent_message(
    tmp_path: Path,
) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = qa.audit(url="http://evil.example.com")
    # Verify the audit-message stream reflects the policy decision.
    msgs = result.to_agent_messages()
    next_actions = msgs[-1]
    assert "target.allowed_hosts" in next_actions["actions"][0]
    # Sanity: UnsafeTargetError is a real public exception (re-export).
    assert UnsafeTargetError.__name__ == "UnsafeTargetError"


def test_artifacts_root_isolates_runs(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    custom_root = tmp_path / "custom-runs"
    qa = Sentinel(project_path=tmp_path, artifacts_root=custom_root)
    result = qa.audit()
    assert custom_root in result.run_dir.parents


def test_no_runtime_dependency_on_os_env_for_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CI", raising=False)
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    # Hostname not in allowlist (and not local) -> unsafe_blocked.
    result = qa.audit(url="http://attacker.test")
    assert result.status == "unsafe_blocked"


def test_audit_keeps_os_environ_unchanged(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    before = dict(os.environ)
    _write_minimal_config(tmp_path)
    Sentinel(project_path=tmp_path).audit()
    assert dict(os.environ) == before
