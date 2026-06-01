"""``sentinel audit --compliance-pack`` CLI surface."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


@pytest.fixture(autouse=True)
def _ensure_compliance_registered() -> None:
    """Re-register the compliance module before every test.

    Other tests in the suite call ``default_registry.clear`` to
    isolate their fixtures; that wipes the compliance module out and
    the audit lifecycle would silently skip it. Re-registering here
    guarantees the pack DSL has a module to dispatch to regardless of
    earlier suite state.
    """

    from engine.orchestrator.registry import default_registry

    from modules.compliance import register_with_default_registry

    register_with_default_registry(default_registry())


def _run_audit(
    runner: CliRunner,
    project: Path,
    *args: str,
) -> tuple[int, str, str]:
    cli = build_app()
    cwd = os.getcwd()
    os.chdir(project)
    try:
        result = runner.invoke(cli, list(args))
    finally:
        os.chdir(cwd)
    return result.exit_code, result.stdout, (result.stderr or "")


def test_audit_with_wcag_22_pack_succeeds(runner: CliRunner, tmp_path: Path) -> None:
    """The wcag-2.2-aa pack loads and emits the pack id in stdout.

    The full compliance/index.json artifact is checked separately by the
    soc2-trail-pack test (this one composes accessibility + compliance;
    accessibility's runner needs a real ``sentinel-ts`` binary, which
    isn't always present in the test environment).
    """

    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    exit_code, stdout, _stderr = _run_audit(
        runner,
        project,
        "audit",
        "--compliance-pack",
        "wcag-2.2-aa",
        "--modules",
        "compliance",
        "--output",
        str(tmp_path / "runs"),
    )
    # Pack id is always printed regardless of module outcomes.
    assert "wcag-2.2-aa" in stdout
    # The compliance module ran (--modules compliance keeps the pack's
    # accessibility entry out of the dispatch list).
    assert exit_code == 0, stdout
    run_dirs = list((tmp_path / "runs").glob("RUN-*"))
    assert run_dirs
    index_path = run_dirs[0] / "compliance" / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text())
    assert "wcag22" in index["enabled_checks"]


def test_audit_with_soc2_trail_pack_passes_gates(runner: CliRunner, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    exit_code, stdout, stderr = _run_audit(
        runner,
        project,
        "audit",
        "--compliance-pack",
        "soc2-trail",
        "--output",
        str(tmp_path / "runs"),
    )
    assert exit_code == 0, stderr


def test_audit_with_unknown_pack_returns_invalid_config(runner: CliRunner, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    exit_code, _stdout, _stderr = _run_audit(
        runner,
        project,
        "audit",
        "--compliance-pack",
        "not-a-real-pack",
    )
    # EXIT_CONFIG_ERROR (2): bad input, distinct from quality-gate failure (1).
    assert exit_code == 2


def test_audit_with_pack_emits_json_payload(runner: CliRunner, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    exit_code, stdout, _stderr = _run_audit(
        runner,
        project,
        "--json",
        "audit",
        "--compliance-pack",
        "gdpr-baseline",
        "--output",
        str(tmp_path / "runs"),
    )
    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload["command"] == "audit"
    assert payload["compliance_pack"] == "gdpr-baseline"


def test_audit_with_custom_pack_path(runner: CliRunner, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    write_config(project)
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        "pack:\n"
        "  id: my-custom\n"
        "  label: My custom pack (automated)\n"
        "  version: 1\n"
        "  includes:\n"
        "    - module: compliance\n"
        "      checks: [soc2_trail]\n",
        encoding="utf-8",
    )
    exit_code, _stdout, stderr = _run_audit(
        runner,
        project,
        "audit",
        "--compliance-pack",
        str(custom),
        "--output",
        str(tmp_path / "runs"),
    )
    assert exit_code == 0, stderr
