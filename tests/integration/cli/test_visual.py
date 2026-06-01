"""CLI integration tests for ``sentinel visual``."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from typer.testing import CliRunner

from modules.visual.baselines import (
    load_index,
    promote_to_baseline,
    write_index,
)
from sentinel_cli.app import build_app
from tests.integration.cli.conftest import write_config


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _ensure_module_registered() -> None:
    """Some earlier CLI tests clear the process-wide registry; re-register."""

    from modules.visual import register_with_default_registry

    register_with_default_registry()


def _write_png(path: Path, *, size: tuple[int, int], color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")
    return path


def _seed_baseline(
    baselines: Path,
    *,
    viewport: str,
    slug: str,
    src: Path,
) -> None:
    record = promote_to_baseline(
        baselines_dir=baselines,
        viewport=viewport,
        route_slug=slug,
        source_png=src,
        captured_by_run_id="RUN-BASEXXXXXXXX",
        captured_at="2026-05-29T00:00:00+00:00",
    )
    write_index(baselines, [record])


def _invoke(cli_runner: CliRunner, project: Path, *args: str) -> Any:
    app = build_app()
    cwd = os.getcwd()
    os.chdir(project)
    try:
        return cli_runner.invoke(app, list(args))
    finally:
        os.chdir(cwd)


def test_visual_lists_in_help(cli_runner: CliRunner) -> None:
    app = build_app()
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "visual" in result.stdout


def test_visual_diff_match_exits_zero(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    baselines = fresh_project / ".sentinel" / "baselines"
    current = fresh_project / "current"
    src = _write_png(fresh_project / "src.png", size=(8, 8), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", slug="home", src=src)
    _write_png(current / "desktop" / "home.png", size=(8, 8), color=(255, 255, 255))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "diff",
        "--current",
        str(current),
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "module_status" in result.stdout


def test_visual_diff_finds_change_exits_one(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    baselines = fresh_project / ".sentinel" / "baselines"
    current = fresh_project / "current"
    src = _write_png(fresh_project / "src.png", size=(8, 8), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", slug="home", src=src)
    _write_png(current / "desktop" / "home.png", size=(8, 8), color=(0, 0, 0))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "diff",
        "--current",
        str(current),
        "--threshold",
        "0.0001",
    )
    assert result.exit_code == 1, result.stdout + result.stderr


def test_visual_diff_json_emits_payload(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    baselines = fresh_project / ".sentinel" / "baselines"
    current = fresh_project / "current"
    src = _write_png(fresh_project / "src.png", size=(8, 8), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", slug="home", src=src)
    _write_png(current / "desktop" / "home.png", size=(8, 8), color=(255, 255, 255))

    app = build_app()
    cwd = os.getcwd()
    os.chdir(fresh_project)
    try:
        result = cli_runner.invoke(
            app,
            ["--json", "visual", "diff", "--current", str(current)],
        )
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "visual.diff"
    assert payload["exit_code"] == 0


def test_visual_accept_refuses_in_ci(
    cli_runner: CliRunner,
    fresh_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "desktop" / "home.png", size=(4, 4), color=(0, 0, 0))
    monkeypatch.setenv("CI", "true")

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(current),
        "--run-id",
        "RUN-CIATTEMPT00",
    )
    assert result.exit_code == 4
    # Audit-log paper trail (the CI guard always records the attempt).
    audit = current.parent / "audit.log"
    assert audit.exists()
    payload = json.loads(audit.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert payload["event"] == "visual.accept.refused_ci"


def test_visual_accept_refuses_via_explicit_ci_flag(
    cli_runner: CliRunner, fresh_project: Path
) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "desktop" / "home.png", size=(4, 4), color=(0, 0, 0))

    result = _invoke(
        cli_runner,
        fresh_project,
        "--ci",
        "visual",
        "accept",
        "--current",
        str(current),
        "--run-id",
        "RUN-CIFLAGAAAAAA",
    )
    assert result.exit_code == 4


def test_visual_accept_local_promotes(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "mobile" / "home.png", size=(4, 4), color=(100, 100, 100))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(current),
        "--run-id",
        "RUN-LOCALPROMOTE",
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    baselines = fresh_project / ".sentinel" / "baselines"
    assert (baselines / "mobile" / "home.png").exists()
    index = load_index(baselines)
    assert ("mobile", "home") in index
    assert index[("mobile", "home")].captured_by_run_id == "RUN-LOCALPROMOTE"


def test_visual_accept_requires_at_least_one_match(
    cli_runner: CliRunner, fresh_project: Path
) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(current),
        "--viewports",
        "desktop",
    )
    assert result.exit_code == 2


def test_visual_capture_copies_pngs(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    source = fresh_project / "source"
    _write_png(source / "mobile" / "home.png", size=(4, 4), color=(0, 200, 0))
    _write_png(source / "desktop" / "home.png", size=(4, 4), color=(0, 0, 200))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "capture",
        "--from",
        str(source),
        "--run-id",
        "RUN-CAPTUREMMMM",
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    dest = fresh_project / ".sentinel" / "runs" / "RUN-CAPTUREMMMM" / "visual" / "current"
    assert (dest / "mobile" / "home.png").exists()
    assert (dest / "desktop" / "home.png").exists()


def test_visual_capture_missing_source_exits_two(
    cli_runner: CliRunner, fresh_project: Path
) -> None:
    write_config(fresh_project)
    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "capture",
        "--from",
        str(fresh_project / "missing"),
        "--run-id",
        "RUN-MISSCAPTUR",
    )
    assert result.exit_code == 2


def test_visual_accept_missing_current_exits_two(
    cli_runner: CliRunner, fresh_project: Path
) -> None:
    write_config(fresh_project)
    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(fresh_project / "nope"),
    )
    assert result.exit_code == 2


def test_visual_diff_missing_config_exits_two(cli_runner: CliRunner, fresh_project: Path) -> None:
    # No config file written — load_config raises FileNotFoundError.
    result = _invoke(cli_runner, fresh_project, "visual", "diff")
    assert result.exit_code == 2


def test_visual_accept_missing_config_exits_two(cli_runner: CliRunner, fresh_project: Path) -> None:
    current = fresh_project / "current"
    _write_png(current / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))
    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(current),
    )
    assert result.exit_code == 2


def test_visual_diff_url_override(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    baselines = fresh_project / ".sentinel" / "baselines"
    current = fresh_project / "current"
    src = _write_png(fresh_project / "src.png", size=(4, 4), color=(255, 255, 255))
    _seed_baseline(baselines, viewport="desktop", slug="home", src=src)
    _write_png(current / "desktop" / "home.png", size=(4, 4), color=(255, 255, 255))

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "diff",
        "--current",
        str(current),
        "--url",
        "http://127.0.0.1:8080",
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def test_visual_accept_corrupt_index_exits_two(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))
    baselines = fresh_project / ".sentinel" / "baselines"
    baselines.mkdir(parents=True)
    (baselines / "index.json").write_text("not json", encoding="utf-8")

    result = _invoke(
        cli_runner,
        fresh_project,
        "visual",
        "accept",
        "--current",
        str(current),
    )
    assert result.exit_code == 2


def test_visual_accept_json_emits_payload(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    current = fresh_project / "current"
    _write_png(current / "mobile" / "home.png", size=(4, 4), color=(50, 50, 50))

    app = build_app()
    cwd = os.getcwd()
    os.chdir(fresh_project)
    try:
        result = cli_runner.invoke(
            app,
            [
                "--json",
                "visual",
                "accept",
                "--current",
                str(current),
                "--run-id",
                "RUN-JSONACCEPT0",
            ],
        )
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "visual.accept"
    assert payload["promoted"] == 1


def test_visual_capture_json_emits_payload(cli_runner: CliRunner, fresh_project: Path) -> None:
    write_config(fresh_project)
    source = fresh_project / "src"
    _write_png(source / "mobile" / "home.png", size=(4, 4), color=(0, 0, 0))
    app = build_app()
    cwd = os.getcwd()
    os.chdir(fresh_project)
    try:
        result = cli_runner.invoke(
            app,
            [
                "--json",
                "visual",
                "capture",
                "--from",
                str(source),
                "--run-id",
                "RUN-CAPJSONXXXXX",
            ],
        )
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["command"] == "visual.capture"
    assert len(payload["copied"]) == 1
