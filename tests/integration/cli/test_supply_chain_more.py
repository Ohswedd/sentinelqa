"""Extra CLI coverage for `sentinel supply-chain` sub-surfaces."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.supply_chain.models import (
    OsvReport,
    PostinstallReport,
    SbomDocument,
    SupplyChainRunOutcome,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


def _outcome_with_finding() -> SupplyChainRunOutcome:
    """An outcome that yields a high-severity finding so we hit the exit-1 branch."""

    from modules.supply_chain.models import OsvAdvisory, OsvComponentResult

    ts = datetime(2026, 5, 31, tzinfo=UTC)
    return SupplyChainRunOutcome(
        sbom=SbomDocument(
            generated_at=ts,
            project_name="x",
            components_count=0,
            lockfiles=(),
        ),
        osv=OsvReport(
            queried_at=ts,
            components_count=1,
            vulnerabilities=(
                OsvComponentResult(
                    package="requests",
                    version="2.31.0",
                    ecosystem="PyPI",
                    advisories=(OsvAdvisory(id="GHSA-x", severity="critical", summary="critical"),),
                ),
            ),
        ),
        freshness=None,
        postinstall=PostinstallReport(scanned_packages=0, issues=()),
        duration_ms=10,
        incomplete=False,
    )


class _StubSupplyChainModule:
    def __init__(self, outcome: SupplyChainRunOutcome) -> None:
        self._outcome = outcome

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from engine.orchestrator.registry import default_registry

        from modules.supply_chain.module import SupplyChainModule

        outcome = self._outcome

        def factory(cfg: Any, sd: Any) -> Any:
            module = SupplyChainModule(cfg, sd)

            def fake_run_audit(_ctx: Any) -> SupplyChainRunOutcome:
                return outcome

            module._run_audit = fake_run_audit  # type: ignore[method-assign,assignment]
            return module

        default_registry().modules["supply_chain"] = factory


@pytest.fixture
def cli_app() -> Any:
    return build_app()


def test_supply_chain_url_override(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome_with_finding()).install(monkeypatch)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "--url", "http://localhost:9000"],
    )
    # Critical finding → exit 1.
    assert result.exit_code == 1


def test_supply_chain_with_project_root_option(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    project = tmp_path / "child"
    project.mkdir()
    from modules.supply_chain.models import SupplyChainRunOutcome

    ts = datetime(2026, 5, 31, tzinfo=UTC)
    outcome = SupplyChainRunOutcome(
        sbom=SbomDocument(generated_at=ts, project_name="x", components_count=0, lockfiles=()),
        duration_ms=1,
    )
    _StubSupplyChainModule(outcome).install(monkeypatch)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "--project-root", str(project)],
    )
    assert result.exit_code == 0


def test_supply_chain_quiet_mode_omits_human_text(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    ts = datetime(2026, 5, 31, tzinfo=UTC)
    outcome = SupplyChainRunOutcome(
        sbom=SbomDocument(generated_at=ts, project_name="x", components_count=0, lockfiles=()),
        duration_ms=1,
    )
    _StubSupplyChainModule(outcome).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "--quiet", "supply-chain"])
    assert result.exit_code == 0
    assert "run_id" not in result.stdout


def test_supply_chain_sbom_json_mode(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--json", "supply-chain", "sbom", "--out", str(out_dir)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "supply-chain.sbom"
    assert payload["components"] == 1


def test_supply_chain_sbom_quiet_mode(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--quiet", "supply-chain", "sbom", "--out", str(out_dir)],
    )
    assert result.exit_code == 0
    assert "project" not in result.stdout


def test_supply_chain_sbom_missing_config(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Don't write a config; sbom subcommand requires one to read project name.
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "sbom", "--out", str(tmp_path / "out")],
    )
    assert result.exit_code == 2


def test_supply_chain_osv_subcommand_json_mode(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    cfg_path = tmp_path / "sentinel.config.yaml"
    cfg_path.write_text(
        cfg_path.read_text(encoding="utf-8")
        + "policy:\n  supply_chain:\n    osv:\n      enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sbom_dir = tmp_path / "sbom"
    sbom_dir.mkdir()
    sbom_path = sbom_dir / "index.json"
    sbom_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-31T00:00:00Z",
                "project_name": "x",
                "lockfiles": [],
                "components_count": 0,
                "schema_version": "1",
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--json", "supply-chain", "osv", "--sbom", str(sbom_path)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "supply-chain.osv"
    assert payload["skipped"] is True


def test_supply_chain_osv_subcommand_quiet_mode(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    cfg_path = tmp_path / "sentinel.config.yaml"
    cfg_path.write_text(
        cfg_path.read_text(encoding="utf-8")
        + "policy:\n  supply_chain:\n    osv:\n      enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sbom_dir = tmp_path / "sbom"
    sbom_dir.mkdir()
    sbom_path = sbom_dir / "index.json"
    sbom_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-05-31T00:00:00Z",
                "project_name": "x",
                "lockfiles": [],
                "components_count": 0,
                "schema_version": "1",
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        cli_app,
        ["--no-ci", "--quiet", "supply-chain", "osv", "--sbom", str(sbom_path)],
    )
    assert result.exit_code == 0
    assert "components" not in result.stdout


def test_supply_chain_osv_missing_config(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "osv", "--sbom", str(tmp_path / "index.json")],
    )
    assert result.exit_code == 2
