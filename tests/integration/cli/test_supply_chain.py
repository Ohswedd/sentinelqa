"""CLI integration tests for ``sentinel supply-chain``."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from modules.supply_chain.models import (
    FreshnessReport,
    OsvReport,
    PostinstallReport,
    SbomDocument,
    SupplyChainRunOutcome,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


class _StubSupplyChainModule:
    """Returns a canned :class:`SupplyChainRunOutcome` regardless of inputs."""

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

        registry = default_registry()
        registry.modules["supply_chain"] = factory


def _outcome(*, incomplete: bool = False) -> SupplyChainRunOutcome:
    timestamp = datetime(2026, 5, 31, tzinfo=UTC)
    return SupplyChainRunOutcome(
        sbom=SbomDocument(
            generated_at=timestamp,
            project_name="test",
            lockfiles=(),
            components_count=0,
        ),
        osv=OsvReport(queried_at=timestamp, components_count=0, vulnerabilities=()),
        freshness=FreshnessReport(
            checked_at=timestamp,
            threshold_days=180,
            lockfiles=(),
        ),
        postinstall=PostinstallReport(scanned_packages=0, issues=()),
        container=None,
        licenses=None,
        duration_ms=12,
        incomplete=incomplete,
    )


@pytest.fixture
def cli_app() -> Any:
    return build_app()


def test_supply_chain_clean_returns_exit_zero(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome()).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "supply-chain"])
    assert result.exit_code == 0, result.stderr


def test_supply_chain_unknown_check_is_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome()).install(monkeypatch)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "--checks", "bogus"],
    )
    assert result.exit_code == 2


def test_supply_chain_incomplete_is_quality_gate_failed(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome(incomplete=True)).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "supply-chain"])
    assert result.exit_code == 1


def test_supply_chain_json_mode_emits_machine_payload(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome()).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "--json", "supply-chain"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"] == "supply-chain"
    assert payload["findings"] == 0


def test_supply_chain_unsafe_target_blocks(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://example.com")
    monkeypatch.chdir(tmp_path)
    _StubSupplyChainModule(_outcome()).install(monkeypatch)
    result = runner.invoke(cli_app, ["--no-ci", "supply-chain"])
    assert result.exit_code == 4


def test_supply_chain_sbom_subcommand_emits_cyclonedx(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "sbom", "--out", str(out_dir)],
    )
    assert result.exit_code == 0, result.stderr
    assert (out_dir / "index.json").exists()
    assert (out_dir / "requirements.txt.cdx.json").exists()


def test_supply_chain_osv_subcommand_missing_sbom_is_config_error(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path, base_url="http://localhost:8088")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["--no-ci", "supply-chain", "osv", "--sbom", str(tmp_path / "absent.json")],
    )
    assert result.exit_code == 2


def test_supply_chain_osv_subcommand_uses_disabled_path(
    cli_app, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(
        tmp_path,
        base_url="http://localhost:8088",
    )
    # Append the OSV-disabled override.
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
        ["--no-ci", "supply-chain", "osv", "--sbom", str(sbom_path)],
    )
    assert result.exit_code == 0, result.stderr
    out = json.loads((sbom_dir / "vulnerabilities.json").read_text(encoding="utf-8"))
    assert out["skipped"] is True
