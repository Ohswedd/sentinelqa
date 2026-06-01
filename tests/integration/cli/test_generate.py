"""CLI integration tests for ``sentinel generate``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config
from tests.integration.discovery.conftest import discovery_server  # noqa: F401


def test_generate_writes_specs_pageobjects_and_plan_md(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811 — pytest fixture reuse
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--url",
            base_url,
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",  # no node toolchain in unit-test env
            "--no-audit",  # audit-locators tested separately
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    spec_root = fresh_project / "tests" / "sentinel"
    assert spec_root.exists()
    plan_md = spec_root / "sentinel.generated.plan.md"
    assert plan_md.exists()
    body = plan_md.read_text(encoding="utf-8")
    assert "SentinelQA Generated" in body
    assert "## Summary" in body
    # At least one spec was emitted.
    specs = list(spec_root.glob("*.spec.ts"))
    assert len(specs) >= 1
    # First spec carries the banner.
    assert "SentinelQA Generated" in specs[0].read_text(encoding="utf-8")


def test_generate_idempotent_for_same_plan(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-running ``generate`` against the same plan produces byte-identical files.

    We run discovery + planning ONCE, then call ``generate --from-discovery``
    twice so the planner gets the same input graph both times (its IDs are
    auto-generated each pass, but the spec writer must not embed them).
    """

    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)
    cli = build_app()

    # Stage 1: produce a discovery dir we can pin both runs against.
    discover = runner.invoke(
        cli,
        [
            "discover",
            "--url",
            base_url,
            "--max-depth",
            "1",
            "--max-pages",
            "10",
            "--rate-limit",
            "50",
        ],
    )
    assert discover.exit_code == 0, discover.stdout + discover.stderr
    runs_root = fresh_project / ".sentinel" / "runs"
    run_dir = next(iter(runs_root.iterdir()))

    args = [
        "generate",
        "--from-discovery",
        str(run_dir),
        "--out",
        "tests",
        "--source",
        ".",
        "--no-tsc",
        "--no-audit",
    ]
    first = runner.invoke(cli, args)
    assert first.exit_code == 0, first.stdout + first.stderr
    spec_root = fresh_project / "tests" / "sentinel"
    specs_before = sorted(
        (p.name, p.read_text(encoding="utf-8")) for p in spec_root.glob("*.spec.ts")
    )

    second = runner.invoke(cli, args)
    assert second.exit_code == 0, second.stdout + second.stderr
    specs_after = sorted(
        (p.name, p.read_text(encoding="utf-8")) for p in spec_root.glob("*.spec.ts")
    )
    assert specs_before == specs_after


def test_generate_refuses_to_clobber_hand_edited_spec(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

    cli = build_app()
    # Drop a hand-owned file BEFORE generating so the writer trips.
    spec_root = fresh_project / "tests" / "sentinel"
    spec_root.mkdir(parents=True)
    decoy = spec_root / "route_smoke_decoy.spec.ts"
    decoy.write_text("// hand-edited, no banner\n", encoding="utf-8")
    # And the plan.md is also hand-owned.
    (spec_root / "sentinel.generated.plan.md").write_text("hand edited\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "generate",
            "--url",
            base_url,
            "--out",
            "tests",
            "--source",
            ".",
            "--no-tsc",
            "--no-audit",
        ],
    )
    # Plan.md is hand-owned → writer refuses (exit 6).
    assert result.exit_code == 6, result.stdout + result.stderr
    # Decoy untouched.
    assert decoy.read_text(encoding="utf-8") == "// hand-edited, no banner\n"


def test_generate_json_mode_emits_machine_readable_summary(
    runner: CliRunner,
    discovery_server: HTTPServer,  # noqa: F811
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    base_url = discovery_server.url_for("/")
    write_config(fresh_project, base_url=base_url)

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
            "--no-audit",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "generate"
    assert "run_id" in payload
    assert "files" in payload
    assert any("spec.ts" in entry["path"] for entry in payload["files"])


def test_generate_blocked_when_target_unsafe(
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fresh_project)
    # Public target with no allowlist → SafetyPolicy must reject (exit 4).
    # We invoke main so the outermost SentinelError handler maps the
    # raised UnsafeTargetError to its deterministic exit code.
    write_config(fresh_project, base_url="http://localhost:3000")
    from sentinel_cli.main import main

    code = main(
        [
            "generate",
            "--url",
            "https://example.com/",
            "--no-tsc",
            "--no-audit",
        ]
    )
    assert code == 4
