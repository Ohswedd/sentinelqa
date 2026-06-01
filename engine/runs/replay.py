# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Apply a unified diff in an isolated tree and replay the audit (v1.4.0).

The MCP tool ``sentinel.replay_with_change`` calls into this module
with:

* the unified-diff text to apply,
* the run id to replay,
* an optional list of test ids to limit the replay to.

The actual git operations and the lifecycle invocation live behind
small abstractions so this module can be tested without touching
the working tree.

The replay walks four stages:

1. **Materialise** — copy the working tree into a temporary
   directory (or use a git worktree when one is requested).
2. **Apply patch** — pipe the unified diff into ``patch -p1``;
   abort cleanly if the diff doesn't apply.
3. **Run lifecycle** — invoke ``RunLifecycle.execute`` against the
   patched tree, optionally restricting ``requested_modules``.
4. **Diff outcomes** — compare the replayed findings against the
   original run's findings; return the delta.

The default ``replay`` runs the full machinery; tests inject a
stub ``runner`` callable.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.runs.compare import RunComparison, compare_runs
from engine.runs.summary import RunSummary, load_run_summary


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    """One ``replay_with_change`` call."""

    source_run_dir: Path  # the original run we want to replay
    unified_diff: str
    project_root: Path
    test_ids: tuple[str, ...] = ()
    timeout_seconds: float = 600.0


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """The result of a single replay."""

    success: bool
    comparison: RunComparison | None
    new_run_id: str
    rationale: str = ""
    safety_violations: tuple[str, ...] = field(default_factory=tuple)
    raw_patch_output: str = ""


# A runner is a callable ``(patched_root: Path, request: ReplayRequest)``
# that runs the lifecycle and returns the path of the new run dir +
# the captured stdout/stderr for logging. Defined here so tests can
# pass a no-op stub.
Runner = Callable[[Path, ReplayRequest], tuple[Path, str]]


def materialise_tree(project_root: Path, target_dir: Path) -> None:
    """Copy ``project_root`` into ``target_dir`` skipping the noisy bits.

    We use :func:`shutil.copytree` with an ignore filter — `git
    worktree` would be lighter but requires the working tree to be
    clean, which we cannot assume.
    """

    def _ignore(_src: str, names: list[str]) -> list[str]:
        return [
            name
            for name in names
            if name
            in {
                ".git",
                ".venv",
                "venv",
                "node_modules",
                "__pycache__",
                ".mypy_cache",
                ".ruff_cache",
                ".pytest_cache",
                "dist",
                "build",
                ".sentinel",
                ".next",
                ".turbo",
            }
        ]

    shutil.copytree(project_root, target_dir, ignore=_ignore, dirs_exist_ok=True)


def apply_patch(
    patched_root: Path,
    unified_diff: str,
    *,
    runner: object | None = None,
) -> tuple[bool, str]:
    """Pipe ``unified_diff`` into ``patch -p1`` inside ``patched_root``.

    Returns ``(applied, output)``. ``runner`` is a test seam that
    replaces :func:`subprocess.run`.
    """

    if not unified_diff.strip():
        return False, "empty diff"

    run = runner if runner is not None else subprocess.run
    try:
        result = run(  # type: ignore[operator]
            ["patch", "--silent", "-p1", "--no-backup-if-mismatch"],
            cwd=str(patched_root),
            input=unified_diff,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return False, "patch(1) not on PATH"
    except subprocess.TimeoutExpired:
        return False, "patch(1) timed out"

    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "patch failed").strip()
    return True, result.stdout.strip()


def replay(
    request: ReplayRequest,
    *,
    runner: Runner | None = None,
    patch_runner: object | None = None,
    tempdir_factory: Callable[[], str] | None = None,
) -> ReplayOutcome:
    """Run the four-stage replay end to end.

    The ``runner`` callable does the lifecycle invocation; passing
    ``None`` returns a ``ReplayOutcome`` with ``success=False`` and a
    clear rationale so the MCP tool can degrade gracefully.
    """

    factory = tempdir_factory or tempfile.mkdtemp
    patched_root = Path(factory()) / "replay"
    patched_root.mkdir(parents=True, exist_ok=True)
    materialise_tree(request.project_root, patched_root)

    applied, patch_output = apply_patch(patched_root, request.unified_diff, runner=patch_runner)
    if not applied:
        return ReplayOutcome(
            success=False,
            comparison=None,
            new_run_id="",
            rationale=f"patch did not apply: {patch_output}",
            safety_violations=("patch-failed",),
            raw_patch_output=patch_output,
        )

    if runner is None:
        return ReplayOutcome(
            success=False,
            comparison=None,
            new_run_id="",
            rationale="no runner configured; pass runner=... to replay()",
            safety_violations=("no-runner",),
            raw_patch_output=patch_output,
        )

    try:
        new_run_dir, _runner_output = runner(patched_root, request)
    except Exception as exc:
        return ReplayOutcome(
            success=False,
            comparison=None,
            new_run_id="",
            rationale=f"runner raised: {type(exc).__name__}: {exc}",
            safety_violations=("runner-exception",),
            raw_patch_output=patch_output,
        )

    before = load_run_summary(request.source_run_dir)
    after = load_run_summary(new_run_dir)
    comparison = compare_runs(before, after)
    return ReplayOutcome(
        success=True,
        comparison=comparison,
        new_run_id=after.run_id,
        rationale="replay completed",
        safety_violations=(),
        raw_patch_output=patch_output,
    )


def summarise_outcome(outcome: ReplayOutcome) -> dict[str, Any]:
    """Convert a :class:`ReplayOutcome` to a JSON-serialisable dict."""

    payload: dict[str, Any] = {
        "success": outcome.success,
        "new_run_id": outcome.new_run_id,
        "rationale": outcome.rationale,
        "safety_violations": list(outcome.safety_violations),
    }
    if outcome.comparison is not None:
        payload["comparison"] = {
            "before_run_id": outcome.comparison.before_run_id,
            "after_run_id": outcome.comparison.after_run_id,
            "score_delta": outcome.comparison.score_delta,
            "has_regressions": outcome.comparison.has_regressions,
            "new_findings": len(outcome.comparison.new),
            "resolved_findings": len(outcome.comparison.resolved),
            "persistent_findings": len(outcome.comparison.persistent),
        }
    return payload


def _unused() -> RunSummary:  # pragma: no cover - silence unused import warnings
    return None  # type: ignore[return-value]


__all__ = [
    "ReplayOutcome",
    "ReplayRequest",
    "apply_patch",
    "materialise_tree",
    "replay",
    "summarise_outcome",
]
