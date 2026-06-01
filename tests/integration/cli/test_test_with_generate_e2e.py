"""E2E test for ``sentinel test --with-generate`` (08.06 + 08.07).

The test runs the generator chain end-to-end against the
``discovery_server`` fixture, then stubs the ``LocalRunner`` so we don't
have to install Playwright in CI. This proves the wiring works:

 sentinel test --with-generate → discovery → planner → generator
 → write specs → LocalRunner.run

without spawning real browsers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from engine.runner.results import RunnerOutcome, TestExecution
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config
from tests.integration.discovery.conftest import discovery_server  # noqa: F401


def test_with_generate_runs_full_chain(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811 — pytest fixture reuse
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    stub_outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-WGAAAAAAAAAA",
        status="passed",
        tests=(
            TestExecution(
                test_id="t1",
                title="stub",
                file="stub.spec.ts",
                status="passed",
                duration_ms=200,
                retries=0,
            ),
        ),
        duration_ms=200,
        environment=None,
    )

    class _StubRunner:
        def __init__(self, *_a: Any, **_kw: Any) -> None: ...

        def run(self, _invocation: Any) -> RunnerOutcome:
            return stub_outcome

    monkeypatch.setattr("sentinel_cli.commands.test_cmd.LocalRunner", _StubRunner)

    cli = build_app()
    result = runner.invoke(cli, ["test", "--with-generate", "--url", base_url])
    assert result.exit_code == 0, result.stdout + result.stderr

    # Specs were actually generated.
    spec_root = fresh_project / "tests" / "sentinel"
    assert spec_root.exists()
    specs = list(spec_root.glob("*.spec.ts"))
    assert specs, "expected at least one generated spec"
    # Generated specs carry the SentinelQA banner.
    body = specs[0].read_text(encoding="utf-8")
    assert "SentinelQA Generated" in body
