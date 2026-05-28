"""Cover the audit-failure paths in ``sentinel generate``.

We monkey-patch ``audit_specs`` so tests don't require node + the
built TS dist. Two scenarios:

- audit returns warnings → CLI exits 6 and reports the warnings.
- audit subprocess errors out → CLI exits 6 with the error message.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.generator import (
    BrittlenessAuditResult,
    BrittlenessWarning,
    LocatorAuditError,
)
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from sentinel_cli.commands import generate_cmd
from tests.integration.cli.conftest import write_config
from tests.integration.discovery.conftest import discovery_server  # noqa: F401


def test_generate_audit_warnings_exit_6(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    def fake_audit(
        files: object, *, cwd: object = None, executable: object = None, runner: object = None
    ) -> BrittlenessAuditResult:
        return BrittlenessAuditResult(
            files_scanned=1,
            warnings=(
                BrittlenessWarning(
                    file="x.spec.ts", line=1, column=1, message="brittle", snippet=""
                ),
            ),
        )

    monkeypatch.setattr(generate_cmd, "audit_specs", fake_audit)

    cli = build_app()
    result = runner.invoke(
        cli,
        ["generate", "--url", base_url, "--out", "tests", "--source", ".", "--no-tsc"],
    )
    assert result.exit_code == 6, result.stdout + result.stderr


def test_generate_audit_error_exit_6(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    def fake_audit_raises(*_args: object, **_kwargs: object) -> BrittlenessAuditResult:
        raise LocatorAuditError("sentinel-ts not found")

    monkeypatch.setattr(generate_cmd, "audit_specs", fake_audit_raises)

    cli = build_app()
    result = runner.invoke(
        cli,
        ["generate", "--url", base_url, "--out", "tests", "--source", ".", "--no-tsc"],
    )
    assert result.exit_code == 6, result.stdout + result.stderr


def test_generate_audit_warnings_json_mode(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as _json

    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    def fake_audit(
        files: object, *, cwd: object = None, executable: object = None, runner: object = None
    ) -> BrittlenessAuditResult:
        return BrittlenessAuditResult(
            files_scanned=1,
            warnings=(BrittlenessWarning(file="x", line=1, column=1, message="m", snippet=""),),
        )

    monkeypatch.setattr(generate_cmd, "audit_specs", fake_audit)

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "--json",
            "generate",
            "--url",
            base_url,
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
        ],
    )
    assert result.exit_code == 6, result.stdout + result.stderr
    payload = _json.loads(result.stdout.strip())
    assert payload["audit_failed"] is True
