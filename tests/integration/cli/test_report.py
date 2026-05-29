"""`sentinel report` re-render CLI (Phase 15.05)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from engine.orchestrator.registry import LifecyclePhase, default_registry
from engine.orchestrator.run_lifecycle import RunLifecycle
from typer.testing import CliRunner

from sentinel_cli.app import build_app
from tests.unit.scoring.conftest import make_finding


def _write_config(root: Path) -> Path:
    p = root / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: app\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n"
        "report:\n  formats: [json, html, junit, sarif, markdown]\n"
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def _seed_run(tmp_path: Path) -> tuple[Path, str]:
    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.typed_findings = (
            make_finding(
                id="FND-REPORTABCDEF",
                module="accessibility",
                severity="medium",
                run_id=ctx.run_id,
            ),
        )

    registry.register_phase_hook(LifecyclePhase.NORMALIZE_FINDINGS, inject)
    try:
        runs_root = tmp_path / ".sentinel" / "runs"
        lifecycle = RunLifecycle(artifacts_root=runs_root)
        test_run = lifecycle.execute(config)
    finally:
        registry.clear()
    return runs_root, test_run.id


def test_report_rerenders_all_formats(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    run_dir = runs_root / run_id
    # Remove the HTML to prove re-render writes it.
    html_path = run_dir / "report.html"
    if html_path.exists():
        html_path.unlink()
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.stderr + result.stdout
    assert html_path.exists()
    body = html_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in body
    # The re-render also leaves all the JSON artifacts in place.
    for name in ("run.json", "findings.json", "score.json", "junit.xml", "sarif.json", "report.md"):
        assert (run_dir / name).exists()


def test_report_format_filter_limits_outputs(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "html",
            "--format",
            "md",
        ],
    )
    assert result.exit_code == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert set(payload["outputs"].keys()) == {"run", "html", "markdown"}


def test_report_idempotent_rerender(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    args = [
        "report",
        "--run-id",
        run_id,
        "--runs-root",
        str(runs_root),
        "--format",
        "html",
    ]
    result_first = runner.invoke(build_app(), args)
    assert result_first.exit_code == 0
    first = (runs_root / run_id / "report.html").read_text(encoding="utf-8")
    result_second = runner.invoke(build_app(), args)
    assert result_second.exit_code == 0
    second = (runs_root / run_id / "report.html").read_text(encoding="utf-8")
    assert first == second


def test_report_latest_pointer(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--runs-root",
            str(runs_root),
            "--format",
            "html",
        ],
    )
    assert result.exit_code == 0, result.stderr + result.stdout


def test_report_missing_run_dir_is_config_error(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            "RUN-NOPENOPENOPE",
            "--runs-root",
            str(tmp_path / ".sentinel" / "runs"),
        ],
    )
    assert result.exit_code == 2
    assert "run directory not found" in result.stderr


def test_report_empty_format_filter_is_config_error(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "bogus",
        ],
    )
    assert result.exit_code == 2
    assert "empty set" in result.stderr


def test_report_open_skipped_in_ci(tmp_path: Path, monkeypatch) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    # Sentinel webbrowser.open getting called would be a test failure;
    # we monkeypatch to detect.
    opens: list[str] = []
    import webbrowser

    def fake_open(url: str, *args, **kwargs) -> bool:
        opens.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--ci",
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--open",
            "--format",
            "html",
        ],
    )
    assert result.exit_code == 0, result.stderr + result.stdout
    assert opens == []


def test_report_open_calls_webbrowser(tmp_path: Path, monkeypatch) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    opens: list[str] = []
    import webbrowser

    def fake_open(url: str, *args, **kwargs) -> bool:
        opens.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--open",
            "--format",
            "html",
        ],
    )
    assert result.exit_code == 0, result.stderr + result.stdout
    assert len(opens) == 1
    assert opens[0].startswith("file://")


def test_report_json_alias_expands_to_three(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert "run" in payload["outputs"]
    assert "findings" in payload["outputs"]
    assert "score" in payload["outputs"]


def test_report_explain_still_works(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
            "--explain-score",
        ],
    )
    assert result.exit_code == 0
    assert "Score explanation" in result.output
