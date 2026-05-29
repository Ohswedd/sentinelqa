"""``Sentinel`` facade — construction + lazy semantics + signatures."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from sentinelqa import Policy, QualityGate, Sentinel


def test_default_construction(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    assert qa.project_path == tmp_path.resolve()
    assert qa.config_path == tmp_path.resolve() / "sentinel.config.yaml"
    assert qa.machine_readable is False


def test_machine_readable_flag(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path, machine_readable=True)
    assert qa.machine_readable is True


def test_from_config_classmethod(tmp_path: Path) -> None:
    cfg = tmp_path / "custom.yaml"
    cfg.write_text("# placeholder\n", encoding="utf-8")
    qa = Sentinel.from_config(cfg)
    assert qa.config_path == cfg.resolve()
    assert qa.project_path == cfg.resolve().parent


def test_artifacts_root_defaults_under_project(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    assert qa._artifacts_root == (tmp_path / ".sentinel" / "runs").resolve()


def test_artifacts_root_override(tmp_path: Path) -> None:
    custom = tmp_path / "elsewhere"
    qa = Sentinel(project_path=tmp_path, artifacts_root=custom)
    assert qa._artifacts_root == custom.resolve()


@pytest.mark.parametrize(
    "method_name",
    [
        "discover",
        "plan",
        "generate_tests",
        "audit",
        "run_plan",
        "report",
        "verify_fix",
    ],
)
def test_every_sync_method_has_async_counterpart(method_name: str) -> None:
    """Every sync method has an ``async_<name>`` mirror (PRD §14.4)."""

    sync = getattr(Sentinel, method_name)
    async_method = getattr(Sentinel, f"async_{method_name}")
    assert callable(sync)
    assert inspect.iscoroutinefunction(async_method)


def test_policy_view_constructable_from_config_fixture(tmp_path: Path) -> None:
    # Construct a minimal config so policy() round-trips.
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\n"
        "project:\n"
        "  name: facade-test\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "security:\n"
        "  mode: safe\n",
        encoding="utf-8",
    )
    qa = Sentinel(project_path=tmp_path)
    pol = qa.policy()
    assert isinstance(pol, Policy)
    assert isinstance(pol.quality_gate, QualityGate)
    assert pol.base_url == "http://localhost:3000/"
    assert pol.mode == "safe"


def test_verify_fix_is_not_implemented(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    # Construct a minimal RepairSuggestion to pass the signature.
    from engine.domain.repair_suggestion import RepairSuggestion

    suggestion = RepairSuggestion(
        id="RPR-AAAAAAAAAAAA",
        target_test="tests/sentinel/login.spec.ts",
        original="page.locator('button.signin')",
        proposed="page.getByRole('button', { name: /sign in/i })",
        confidence=0.9,
        reason="Brittleness audit flagged the class-based selector.",
    )
    with pytest.raises(NotImplementedError, match="Phase 20"):
        qa.verify_fix("RUN-AAAAAAAAAAAA", suggestion)


def test_plan_requires_exactly_one_of_url_or_graph(tmp_path: Path) -> None:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\n"
        "project:\n"
        "  name: facade-test\n"
        "target:\n"
        "  base_url: http://localhost:3000\n"
        "  allowed_hosts:\n"
        "    - localhost\n"
        "security:\n"
        "  mode: safe\n",
        encoding="utf-8",
    )
    qa = Sentinel(project_path=tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        qa.plan(url=None, graph=None)


def test_report_returns_path_for_resolved_run(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    # Lay down a synthetic run.
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{}", encoding="utf-8")
    result = qa.report(run_id="RUN-AAAAAAAAAAAA")
    assert result == run_dir.resolve()


def test_report_latest_falls_back_to_newest(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    root = tmp_path / ".sentinel" / "runs"
    (root / "RUN-AAAAAAAAAAAA").mkdir(parents=True)
    (root / "RUN-BBBBBBBBBBBB").mkdir(parents=True)
    out = qa.report(latest=True)
    assert out.name == "RUN-BBBBBBBBBBBB"


def test_report_raises_when_no_runs(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    with pytest.raises(FileNotFoundError):
        qa.report(latest=True)


def test_report_raises_when_run_id_missing(tmp_path: Path) -> None:
    qa = Sentinel(project_path=tmp_path)
    with pytest.raises(FileNotFoundError):
        qa.report(run_id="RUN-MISSINGAAAAA")
