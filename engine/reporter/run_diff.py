# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Typed run-to-run diff for the HTML report + the run viewer (v1.6.0).

A thin layer on top of :mod:`scripts.diff_runs`'s normalisation:

* :func:`compute_run_diff` takes two run directories and returns a
  structured :class:`RunDiff` summarising what changed at the
  finding level (new / resolved / persistent / severity changes)
  and at the artifact level (which top-level JSON files differ).
* :func:`render_run_diff_section` produces an HTML fragment the
  Jinja template embeds verbatim, so the report shows "what
  changed since the last green" at the top.

This module is pure (tests inject the two run directories on
``tmp_path``); the I/O is deliberately confined to file reads so it
can run inside the lifecycle's reporter step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from engine.runs.compare import RunComparison, compare_runs
from engine.runs.summary import FindingRef, load_run_summary

_ARTIFACT_NAMES: tuple[str, ...] = (
    "run.json",
    "findings.json",
    "score.json",
    "plan.json",
    "discovery.json",
    "cache.json",
)


@dataclass(frozen=True, slots=True)
class ArtifactDelta:
    """One artifact-level delta between two runs."""

    artifact: str
    before_bytes: int
    after_bytes: int
    changed: bool


@dataclass(frozen=True, slots=True)
class RunDiff:
    """The full diff between two completed runs."""

    before_run_id: str
    after_run_id: str
    comparison: RunComparison
    artifact_deltas: tuple[ArtifactDelta, ...] = field(default_factory=tuple)

    @property
    def has_changes(self) -> bool:
        return (
            bool(self.comparison.new)
            or bool(self.comparison.resolved)
            or bool(self.comparison.severity_changes)
            or any(d.changed for d in self.artifact_deltas)
        )


def _artifact_size(run_dir: Path, name: str) -> int:
    path = run_dir / name
    if not path.is_file():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def compute_run_diff(before_dir: Path, after_dir: Path) -> RunDiff:
    """Build a structured :class:`RunDiff` for two run directories."""

    before_summary = load_run_summary(before_dir)
    after_summary = load_run_summary(after_dir)
    comparison = compare_runs(before_summary, after_summary)

    deltas: list[ArtifactDelta] = []
    for name in _ARTIFACT_NAMES:
        before_size = _artifact_size(before_dir, name)
        after_size = _artifact_size(after_dir, name)
        if before_size == 0 and after_size == 0:
            continue
        deltas.append(
            ArtifactDelta(
                artifact=name,
                before_bytes=before_size,
                after_bytes=after_size,
                changed=before_size != after_size,
            )
        )

    return RunDiff(
        before_run_id=before_summary.run_id,
        after_run_id=after_summary.run_id,
        comparison=comparison,
        artifact_deltas=tuple(deltas),
    )


# --------------------------------------------------------------------------- #
# HTML fragment rendering — kept simple so it can land in the Jinja template
# --------------------------------------------------------------------------- #


def _row(label: str, count: int, css_class: str) -> str:
    return f'<tr class="{css_class}">' f"<th>{escape(label)}</th>" f"<td>{count}</td>" f"</tr>"


def _findings_table(title: str, rows: tuple[FindingRef, ...], css_class: str) -> str:
    if not rows:
        return ""
    body = "".join(
        f"<tr><td>{escape(r.module)}</td>"
        f'<td><span class="sev sev-{escape(r.severity)}">{escape(r.severity)}</span></td>'
        f"<td>{escape(r.title)}</td></tr>"
        for r in rows
    )
    return (
        f'<section class="run-diff-list {css_class}">'
        f"<h3>{escape(title)} ({len(rows)})</h3>"
        '<table class="run-diff-findings">'
        "<thead><tr><th>Module</th><th>Severity</th><th>Title</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</section>"
    )


def render_run_diff_section(diff: RunDiff) -> str:
    """Render a self-contained HTML ``<section>`` describing the diff.

    The fragment is safe to inline into any host page — every value
    flows through :func:`html.escape` and the only added CSS classes
    are namespaced with ``run-diff-``.
    """

    if not diff.has_changes:
        return (
            '<section class="run-diff run-diff-clean">'
            "<h2>Run-to-run diff</h2>"
            f'<p class="run-diff-empty">No findings or artifacts changed '
            f"between <code>{escape(diff.before_run_id)}</code> and "
            f"<code>{escape(diff.after_run_id)}</code>.</p>"
            "</section>"
        )

    summary_rows = (
        _row("New findings", len(diff.comparison.new), "diff-new"),
        _row("Resolved findings", len(diff.comparison.resolved), "diff-resolved"),
        _row("Persistent findings", len(diff.comparison.persistent), "diff-persistent"),
        _row(
            "Severity regressions",
            sum(1 for c in diff.comparison.severity_changes if c.direction == "regressed"),
            "diff-regression",
        ),
        _row(
            "Severity improvements",
            sum(1 for c in diff.comparison.severity_changes if c.direction == "improved"),
            "diff-improvement",
        ),
    )
    summary = (
        '<table class="run-diff-summary">'
        "<thead><tr><th>Change</th><th>Count</th></tr></thead>"
        "<tbody>" + "".join(summary_rows) + "</tbody>"
        "</table>"
    )
    score_line = ""
    if diff.comparison.score_delta is not None:
        direction = "+" if diff.comparison.score_delta >= 0 else ""
        score_line = (
            '<p class="run-diff-score">Quality-score delta: '
            f"<strong>{direction}{diff.comparison.score_delta:.1f}</strong></p>"
        )
    new_block = _findings_table("New", diff.comparison.new, "run-diff-new")
    resolved_block = _findings_table("Resolved", diff.comparison.resolved, "run-diff-resolved")

    return (
        '<section class="run-diff">'
        "<h2>Run-to-run diff</h2>"
        f'<p class="run-diff-headline">'
        f"Comparing <code>{escape(diff.before_run_id)}</code> &rarr; "
        f"<code>{escape(diff.after_run_id)}</code>.</p>"
        f"{score_line}"
        f"{summary}"
        f"{new_block}"
        f"{resolved_block}"
        "</section>"
    )


__all__ = [
    "ArtifactDelta",
    "RunDiff",
    "compute_run_diff",
    "render_run_diff_section",
]
