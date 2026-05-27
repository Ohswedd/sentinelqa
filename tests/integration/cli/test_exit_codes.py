"""Every documented exit code is reachable from the CLI (task 02.06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSAFE_TARGET,
)

from sentinel_cli.main import main


def _invoke_main(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    return main(argv)


def test_exit_0_success(
    fresh_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(fresh_project)
    code = _invoke_main(
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "init",
            "--path",
            str(fresh_project),
        ],
        monkeypatch,
    )
    assert code == EXIT_SUCCESS


def test_exit_2_invalid_config(
    fresh_project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = fresh_project / "sentinel.config.yaml"
    cfg.write_text("project: {{ not-yaml", encoding="utf-8")
    code = _invoke_main(["--config", str(cfg), "audit"], monkeypatch)
    assert code == EXIT_CONFIG_ERROR


def test_exit_4_unsafe_target(fresh_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = fresh_project / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: bad\n"
        "target:\n  base_url: https://example.com\n  allowed_hosts: []\n",
        encoding="utf-8",
    )
    code = _invoke_main(["--config", str(cfg), "doctor"], monkeypatch)
    assert code == EXIT_UNSAFE_TARGET


def test_exit_5_dependency_missing(fresh_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = fresh_project / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "auth:\n  strategy: test_user\n"
        "  username_env: NEVER_SET_FOR_TEST_AAA\n"
        "  password_env: NEVER_SET_FOR_TEST_BBB\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("NEVER_SET_FOR_TEST_AAA", raising=False)
    monkeypatch.delenv("NEVER_SET_FOR_TEST_BBB", raising=False)
    code = _invoke_main(["--config", str(cfg), "doctor"], monkeypatch)
    assert code == EXIT_DEPENDENCY_MISSING


def test_exit_7_internal_error_from_stub(
    fresh_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = fresh_project / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    # Any stub command (e.g. `report`) raises InternalError → exit 7.
    code = _invoke_main(["--config", str(cfg), "report"], monkeypatch)
    assert code == EXIT_INTERNAL_ERROR


def test_exit_1_quality_gate_failure(fresh_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive the lifecycle into a `failed` status via a phase hook to prove
    the audit command maps `failed` → exit code 1.

    Phase 14 ships the real quality-score engine; here we use the registry's
    APPLY_QUALITY_GATES hook to flip `ctx.quality_gate_passed` so the
    deterministic `failed` → exit-1 mapping is exercised today.
    """

    from engine.errors.codes import EXIT_QUALITY_GATE_FAILED
    from engine.orchestrator.registry import LifecyclePhase, default_registry

    cfg = fresh_project / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )

    registry = default_registry()
    registry.clear()

    def fail_gate(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.quality_gate_passed = False

    registry.register_phase_hook(LifecyclePhase.APPLY_QUALITY_GATES, fail_gate)
    try:
        code = _invoke_main(["--config", str(cfg), "audit"], monkeypatch)
    finally:
        registry.clear()

    assert code == EXIT_QUALITY_GATE_FAILED
