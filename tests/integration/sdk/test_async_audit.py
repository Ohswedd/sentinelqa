"""Async/sync parity for the SDK (our product spec4, task 16.04)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from engine.orchestrator.registry import ModuleRegistry, default_registry

from sentinelqa import AuditResult, Sentinel


def _write_minimal_config(root: Path) -> Path:
    config_path = root / "sentinel.config.yaml"
    config_path.write_text(
        "version: 1\n"
        "project:\n"
        "  name: sdk-async-fixture\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
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
    reg = default_registry()
    prior = reg.modules.get("functional")
    reg.register_module("functional", lambda cfg, decision: {"ok": True})
    try:
        yield reg
    finally:
        if prior is not None:
            reg.register_module("functional", prior)
        else:
            reg.modules.pop("functional", None)


def test_async_audit_runs(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    result = asyncio.run(qa.async_audit())
    assert isinstance(result, AuditResult)
    assert result.passed is True


def test_sync_and_async_produce_equivalent_results(
    tmp_path: Path,
    patched_registry: ModuleRegistry,
) -> None:
    """Two calls via the two API surfaces produce the same shape.

    Sync forms wrap ``asyncio.run`` and so cannot be called from a
    running event loop — this test runs in a synchronous context to
    exercise both paths back-to-back without nesting loops.
    """

    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    sync_result = qa.audit()
    async_result = asyncio.run(qa.async_audit())
    # IDs differ (new run id per call) but shape + status must match.
    assert async_result.status == sync_result.status
    assert async_result.passed == sync_result.passed
    assert async_result.modules_run == sync_result.modules_run
    assert async_result.release_decision == sync_result.release_decision


def test_async_report_returns_run_dir(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    audit = asyncio.run(qa.async_audit())
    resolved = asyncio.run(qa.async_report(run_id=audit.run_id))
    assert resolved == audit.run_dir


def test_async_verify_fix_raises_not_implemented(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    from engine.domain.repair_suggestion import RepairSuggestion

    suggestion = RepairSuggestion(
        id="RPR-AAAAAAAAAAAA",
        target_test="tests/sentinel/x.spec.ts",
        original="page.locator('button')",
        proposed="page.getByRole('button')",
        confidence=0.9,
        reason="Brittleness.",
    )
    with pytest.raises(NotImplementedError, match="Phase 20"):
        asyncio.run(qa.async_verify_fix("RUN-AAAAAAAAAAAA", suggestion))


def test_sync_form_uses_asyncio_run(tmp_path: Path, patched_registry: ModuleRegistry) -> None:
    """The synchronous methods MUST work even when there is no running loop."""

    _write_minimal_config(tmp_path)
    qa = Sentinel(project_path=tmp_path)
    # Verify there's no current loop, then call the sync form.
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False
    assert not running
    result = qa.audit()
    assert result.passed
