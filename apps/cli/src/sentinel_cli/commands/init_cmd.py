"""`sentinel init` command (task 02.02).

Scaffolds a new SentinelQA project: writes `sentinel.config.yaml`,
patches `.gitignore`, creates `.sentinel/` runtime tree, and drops a
starter GitHub Action. Idempotent — re-running is a no-op unless
`--force` is supplied.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from engine.config.loader import dump_config

from sentinel_cli import init_detect
from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

# The GitHub Action template lives in the documentation. Whenever the PRD copy
# changes, this constant MUST be updated in the same commit (CLAUDE §5).
# Tests assert byte-for-byte equality between this constant and the PRD
# block.
GITHUB_ACTION_TEMPLATE = """name: SentinelQA

on:
  pull_request:
  push:
    branches: [main]

jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - uses: actions/setup-python@v5
      - run: npm install
      - run: npx playwright install --with-deps
      - run: pip install sentinelqa
      - run: sentinel ci --url ${{ secrets.PREVIEW_URL }} --diff origin/main...HEAD
"""


GITIGNORE_ENTRIES = (
    ".sentinel/runs/",
    ".sentinel/cache/",
    ".sentinel/reports/",
)

SENTINEL_DOT_GITIGNORE = "runs/\ncache/\nreports/\nbaselines/\n"


def run_init(
    ctx: typer.Context,
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            help="Project root to scaffold into.",
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing files."),
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive",
            help="Never prompt; fall back to safe defaults on detection misses.",
        ),
    ] = False,
) -> None:
    """Implement the `init` command."""

    state: GlobalState = ctx.obj
    del non_interactive  # reserved for future interactive features

    actions: list[dict[str, Any]] = []

    detection = init_detect.detect(path)

    config_yaml = init_detect.render_config(
        project_root=path,
        detection=detection,
        dump_config=dump_config,
    )

    config_path = path / "sentinel.config.yaml"
    actions.append(_write_if_needed(config_path, config_yaml, force=force))

    actions.append(_ensure_dir(path / "tests" / "sentinel"))
    actions.append(_ensure_dir(path / ".sentinel"))
    actions.append(
        _write_if_needed(
            path / ".sentinel" / ".gitignore",
            SENTINEL_DOT_GITIGNORE,
            force=force,
        )
    )

    workflow_dir = path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    actions.append(
        _write_if_needed(
            workflow_dir / "sentinel.yml",
            GITHUB_ACTION_TEMPLATE,
            force=force,
        )
    )

    actions.append(_patch_gitignore(path / ".gitignore"))

    next_steps = (
        "Next: run `sentinel doctor` to verify the environment, "
        "then `sentinel audit --url <BASE_URL>` to perform your first run."
    )

    if state.mode == "json":
        with json_stdout() as out:
            out.emit({"command": "init", "path": str(path), "actions": actions})
    elif state.mode != "quiet":
        for action in actions:
            sys.stdout.write(f"{action['status']:>8}  {action['path']}\n")
        sys.stdout.write("\n" + next_steps + "\n")


def _write_if_needed(path: Path, content: str, *, force: bool) -> dict[str, Any]:
    if path.exists() and not force:
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return {"action": "write", "path": str(path), "status": "unchanged"}
        return {"action": "write", "path": str(path), "status": "skipped (exists; use --force)"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"action": "write", "path": str(path), "status": "wrote" if not force else "overwrote"}


def _ensure_dir(path: Path) -> dict[str, Any]:
    if path.exists():
        return {"action": "mkdir", "path": str(path), "status": "unchanged"}
    path.mkdir(parents=True, exist_ok=True)
    return {"action": "mkdir", "path": str(path), "status": "created"}


def _patch_gitignore(gitignore: Path) -> dict[str, Any]:
    existing_lines: list[str] = []
    if gitignore.exists():
        existing_lines = gitignore.read_text(encoding="utf-8").splitlines()

    needed = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    if not needed:
        return {"action": "gitignore", "path": str(gitignore), "status": "unchanged"}

    block_header = "# SentinelQA"
    new_lines = list(existing_lines)
    if block_header not in new_lines:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(block_header)
    new_lines.extend(needed)
    new_lines.append("")

    gitignore.write_text("\n".join(new_lines), encoding="utf-8")
    return {
        "action": "gitignore",
        "path": str(gitignore),
        "status": f"appended {len(needed)} entr{'y' if len(needed) == 1 else 'ies'}",
    }


__all__ = ["run_init", "GITHUB_ACTION_TEMPLATE", "GITIGNORE_ENTRIES"]
