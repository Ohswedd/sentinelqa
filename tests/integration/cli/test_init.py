"""`sentinel init` scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config.loader import load_config
from typer.testing import CliRunner

from sentinel_cli.commands.init_cmd import GITHUB_ACTION_TEMPLATE, GITIGNORE_ENTRIES


def _invoke_init(runner: CliRunner, cli, project: Path, *extra: str):
    return runner.invoke(
        cli,
        [
            "--config",
            str(project / "sentinel.config.yaml"),
            "init",
            "--path",
            str(project),
            *extra,
        ],
    )


def test_init_fresh_repo_writes_full_scaffold(runner: CliRunner, cli, fresh_project: Path) -> None:
    result = _invoke_init(runner, cli, fresh_project)
    assert result.exit_code == 0, result.stderr

    config_path = fresh_project / "sentinel.config.yaml"
    assert config_path.exists()
    workflow = fresh_project / ".github" / "workflows" / "sentinel.yml"
    assert workflow.exists()
    assert workflow.read_text(encoding="utf-8") == GITHUB_ACTION_TEMPLATE
    assert (fresh_project / "tests" / "sentinel").is_dir()
    assert (fresh_project / ".sentinel").is_dir()
    assert (
        (fresh_project / ".sentinel" / ".gitignore").read_text(encoding="utf-8").startswith("runs/")
    )

    # Loader accepts the generated config.
    config = load_config(config_path)
    assert config.project.name


def test_init_is_idempotent(runner: CliRunner, cli, fresh_project: Path) -> None:
    first = _invoke_init(runner, cli, fresh_project)
    assert first.exit_code == 0, first.stderr

    config_path = fresh_project / "sentinel.config.yaml"
    workflow = fresh_project / ".github" / "workflows" / "sentinel.yml"
    config_before = config_path.read_text(encoding="utf-8")
    workflow_before = workflow.read_text(encoding="utf-8")
    workflow_mtime_before = workflow.stat().st_mtime

    second = _invoke_init(runner, cli, fresh_project)
    assert second.exit_code == 0, second.stderr

    assert config_path.read_text(encoding="utf-8") == config_before
    assert workflow.read_text(encoding="utf-8") == workflow_before
    # Files were not rewritten; mtime preserved.
    assert workflow.stat().st_mtime == workflow_mtime_before


def test_init_force_overwrites(runner: CliRunner, cli, fresh_project: Path) -> None:
    config_path = fresh_project / "sentinel.config.yaml"
    config_path.write_text("# previous content\n", encoding="utf-8")

    result = _invoke_init(runner, cli, fresh_project, "--force")
    assert result.exit_code == 0, result.stderr

    new_body = config_path.read_text(encoding="utf-8")
    assert "previous content" not in new_body
    assert "project:" in new_body


def test_init_gitignore_dedups(runner: CliRunner, cli, fresh_project: Path) -> None:
    gi = fresh_project / ".gitignore"
    gi.write_text("# existing\nnode_modules/\n.sentinel/runs/\n", encoding="utf-8")

    result = _invoke_init(runner, cli, fresh_project)
    assert result.exit_code == 0, result.stderr

    body = gi.read_text(encoding="utf-8")
    # `.sentinel/runs/` was already there — it should NOT be duplicated.
    assert body.count(".sentinel/runs/") == 1
    # Other SentinelQA entries got appended.
    for entry in GITIGNORE_ENTRIES:
        assert entry in body


def test_init_json_mode_emits_single_object(runner: CliRunner, cli, fresh_project: Path) -> None:
    result = runner.invoke(
        cli,
        [
            "--config",
            str(fresh_project / "sentinel.config.yaml"),
            "--json",
            "init",
            "--path",
            str(fresh_project),
        ],
    )
    assert result.exit_code == 0, result.stderr
    lines = [ln for ln in result.stdout.strip().splitlines() if ln]
    assert len(lines) == 1, lines
    payload = json.loads(lines[0])
    assert payload["command"] == "init"
    assert "actions" in payload


def test_init_existing_package_json_detected(runner: CliRunner, cli, fresh_project: Path) -> None:
    (fresh_project / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"next": "14"}}),
        encoding="utf-8",
    )
    result = _invoke_init(runner, cli, fresh_project)
    assert result.exit_code == 0, result.stderr
    config = load_config(fresh_project / "sentinel.config.yaml")
    assert config.project.framework == "nextjs"
    assert config.project.name == "demo"
