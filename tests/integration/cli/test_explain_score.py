"""Task 14.06 — `sentinel report --explain-score` integration tests."""

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
        "modules:\n  functional: false\n  api: false\n  accessibility: false\n"
        "  performance: false\n  visual: false\n  security: false\n"
        "  chaos: false\n  llm_audit: false\n",
        encoding="utf-8",
    )
    return p


def _seed_run(tmp_path: Path) -> tuple[Path, str]:
    """Execute a lifecycle with a known finding and return runs-root + id."""

    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.typed_findings = (
            make_finding(
                id="FND-EXPLAINAAA01",
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


def test_explain_score_human_output(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Score explanation" in result.output
    assert run_id in result.output
    assert "Per-axis contribution" in result.output
    # Markdown was written next to score.json.
    explanation_path = runs_root / run_id / "score-explanation.md"
    assert explanation_path.exists()
    md = explanation_path.read_text(encoding="utf-8")
    assert "# Score explanation" in md
    assert "## Per-axis contribution" in md


def test_explain_score_json_mode_matches_score_json(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    score_payload = json.loads((runs_root / run_id / "score.json").read_text(encoding="utf-8"))

    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "--json",
            "report",
            "--explain-score",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.output
    json_line = result.output.strip().splitlines()[-1]
    payload = json.loads(json_line)
    assert payload["run_id"] == run_id
    assert payload["total"] == score_payload["total"]
    assert payload["components"] == score_payload["components"]
    assert payload["severity_penalties"] == score_payload["severity_penalties"]
    assert payload["blockers"] == score_payload["blockers"]
    assert payload["release_decision"] == score_payload["release_decision"]
    # Breakdown rows mirror components & weights from the persisted file.
    rebuilt = {row["axis"]: row["contribution"] for row in payload["breakdown"]}
    for axis, component in score_payload["components"].items():
        expected = round(component * score_payload["weights"][axis], 4)
        assert rebuilt[axis] == expected


def test_explain_score_missing_run_id_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--run-id",
            "RUN-MISSINGAAAAA",
            "--runs-root",
            str(tmp_path / ".sentinel" / "runs"),
        ],
    )
    assert result.exit_code == 2, result.output  # EXIT_CONFIG_ERROR


def test_explain_score_without_flag_is_phase_15_error(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--run-id",
            "RUN-DOESNOTEXIST",
            "--runs-root",
            str(tmp_path / ".sentinel" / "runs"),
        ],
    )
    # Without --explain-score we surface the Phase-15 not-yet-implemented
    # error (exit code 7), not a silent success.
    assert result.exit_code == 7, result.output


def test_explain_score_latest_fallback(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    # Lifecycle update_latest_pointer writes either a symlink or a marker;
    # either way score.json should be reachable through `latest`.
    latest_score = runs_root / "latest" / "score.json"
    assert latest_score.exists() or (runs_root / "latest").is_symlink()

    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Score explanation" in result.output


def test_explain_score_quiet_emits_nothing_to_stdout(tmp_path: Path) -> None:
    runs_root, run_id = _seed_run(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "--quiet",
            "report",
            "--explain-score",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.output
    # Quiet mode: no human output on stdout, but the markdown is still written.
    assert "Score explanation" not in result.output
    assert (runs_root / run_id / "score-explanation.md").exists()


def test_explain_score_blocker_section_present_for_blocked_run(tmp_path: Path) -> None:
    """Cover the blocker rendering branches in both human + markdown output."""

    config = load_config(_write_config(tmp_path))
    registry = default_registry()
    registry.clear()

    def inject(ctx) -> None:  # type: ignore[no-untyped-def]
        ctx.typed_findings = (
            make_finding(
                id="FND-CRITBLKAAA01",
                module="security",
                severity="critical",
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

    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--run-id",
            test_run.id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Blockers (finding ids):" in result.output
    assert "FND-" in result.output
    md = (runs_root / test_run.id / "score-explanation.md").read_text(encoding="utf-8")
    assert "## Blockers" in md
    assert "`FND-" in md


def test_explain_score_corrupt_json_errors(tmp_path: Path) -> None:
    """Score files that aren't valid JSON exit 2 with a clear error."""

    runs_root = tmp_path / ".sentinel" / "runs"
    run_id = "RUN-CORRUPTAAAAA"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "score.json").write_text("{not valid json", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "could not parse" in result.output


def test_explain_score_missing_key_errors(tmp_path: Path) -> None:
    """Truncated score.json (missing required key) exits 2."""

    runs_root = tmp_path / ".sentinel" / "runs"
    run_id = "RUN-TRUNCATEAAAA"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "score.json").write_text('{"run_id": "RUN-TRUNCATEAAAA"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        build_app(),
        [
            "report",
            "--explain-score",
            "--run-id",
            run_id,
            "--runs-root",
            str(runs_root),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "missing required key" in result.output
