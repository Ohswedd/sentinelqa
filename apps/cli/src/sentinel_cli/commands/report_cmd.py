"""`sentinel report --explain-score` (task 14.06).

Phase 14 ships the **score explainer** only. The broader HTML / JSON
re-render workflow (with PR-comment posting) lands in Phase 15; calling
``sentinel report`` without ``--explain-score`` is a config error
rather than a silent no-op (CLAUDE.md §37: no fake completion).

The explainer reads ``score.json`` from a specific run directory (or
the ``latest`` symlink), expands the math behind every component +
penalty + blocker into human-readable form, prints the same data to
stdout (human or JSON), and writes a deterministic
``score-explanation.md`` next to the source ``score.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any

import typer
from engine.errors.codes import EXIT_CONFIG_ERROR, EXIT_INTERNAL_ERROR, EXIT_SUCCESS

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState


def run_report(
    ctx: typer.Context,
    explain_score: Annotated[
        bool,
        typer.Option(
            "--explain-score",
            help=(
                "Print the math behind score.json (Phase 14). "
                "Other report rendering modes land in Phase 15."
            ),
        ),
    ] = False,
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Run id (e.g. RUN-XXXXXXXXXXXX). Defaults to --latest.",
        ),
    ] = None,
    latest: Annotated[
        bool,
        typer.Option(
            "--latest/--no-latest",
            help="Resolve from `.sentinel/runs/latest`. Implied when --run-id is omitted.",
        ),
    ] = False,
    runs_root: Annotated[
        Path,
        typer.Option(
            "--runs-root",
            help="Override the artifact root (default `.sentinel/runs`).",
        ),
    ] = Path(".sentinel/runs"),
) -> None:
    """Render the Phase-14 score explanation for a completed run."""

    state: GlobalState = ctx.obj
    if not explain_score:
        typer.echo(
            "`sentinel report` currently only supports --explain-score (Phase 14). "
            "Full HTML/JSON re-rendering lands in Phase 15.",
            err=True,
        )
        raise typer.Exit(code=EXIT_INTERNAL_ERROR)

    try:
        score_path = _resolve_score_path(runs_root, run_id=run_id, latest=latest)
        payload = _load_score(score_path)
    except _ExplainError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from None
    breakdown = _build_breakdown(payload)
    markdown = _render_markdown(payload, breakdown)
    explanation_path = score_path.parent / "score-explanation.md"
    explanation_path.write_text(markdown, encoding="utf-8")

    if state.json:
        with json_stdout() as stream:
            stream.emit(
                {
                    "run_id": payload["run_id"],
                    "score_path": str(score_path),
                    "explanation_path": str(explanation_path),
                    "release_decision": payload["release_decision"],
                    "total": payload["total"],
                    "components": payload["components"],
                    "weights": payload["weights"],
                    "severity_penalties": payload["severity_penalties"],
                    "blockers": payload["blockers"],
                    "policy": payload["policy"],
                    "breakdown": breakdown,
                }
            )
    elif not state.quiet:
        typer.echo(_render_human(payload, breakdown))
        typer.echo(f"\nWrote {explanation_path}")

    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ExplainError(Exception):
    """Internal sentinel raised from helpers; mapped to exit 2 at the boundary."""


def _resolve_score_path(
    runs_root: Path,
    *,
    run_id: str | None,
    latest: bool,
) -> Path:
    del latest  # `latest` is the default when --run-id is omitted.
    if run_id is not None:
        candidate = runs_root / run_id / "score.json"
    else:
        candidate = runs_root / "latest" / "score.json"
    if not candidate.exists():
        raise _ExplainError(f"score.json not found at {candidate}. Run a non-dry-run audit first.")
    return candidate


def _load_score(path: Path) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _ExplainError(f"could not parse {path}: {exc}") from exc
    for key in (
        "run_id",
        "total",
        "components",
        "weights",
        "severity_penalties",
        "blockers",
        "release_decision",
        "policy",
    ):
        if key not in payload:
            raise _ExplainError(f"score.json is missing required key {key!r}.")
    return payload


def _build_breakdown(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Per-axis contribution: ``component * weight``, rounded."""

    components: Mapping[str, float] = payload["components"]
    weights: Mapping[str, float] = payload["weights"]
    rows: list[dict[str, Any]] = []
    for axis in sorted(components):
        component = float(components[axis])
        weight = float(weights.get(axis, 0.0))
        contribution = round(component * weight, 4)
        rows.append(
            {
                "axis": axis,
                "component": component,
                "weight": weight,
                "contribution": contribution,
            }
        )
    return rows


def _render_human(payload: Mapping[str, Any], breakdown: Sequence[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"Score explanation for {payload['run_id']}")
    lines.append("=" * 60)
    total = payload["total"]
    total_repr = "N/A" if total is None else f"{float(total):.2f}"
    lines.append(f"Total quality score : {total_repr}")
    lines.append(f"Release decision    : {payload['release_decision']}")
    lines.append("")
    lines.append("Per-axis contribution (component * weight)")
    lines.append("-" * 60)
    lines.append(f"  {'axis':<14} {'component':>10} {'weight':>8} {'contrib':>10}")
    for row in breakdown:
        lines.append(
            f"  {row['axis']:<14} "
            f"{row['component']:>10.4f} {row['weight']:>8.4f} {row['contribution']:>10.4f}"
        )
    lines.append("")
    lines.append("Severity penalties applied")
    lines.append("-" * 60)
    for bucket in ("critical", "high", "medium", "low", "info"):
        applied = float(payload["severity_penalties"].get(bucket, 0.0))
        lines.append(f"  {bucket:<10} {applied:>10.4f}")
    lines.append("")
    blockers: list[str] = list(payload["blockers"])
    if blockers:
        lines.append("Blockers (finding ids):")
        for fid in blockers:
            lines.append(f"  - {fid}")
    else:
        lines.append("Blockers: none.")
    lines.append("")
    policy = payload["policy"]
    lines.append("Policy thresholds")
    lines.append("-" * 60)
    lines.append(f"  min_quality_score      : {policy.get('min_quality_score')}")
    lines.append(f"  block_on_critical      : {policy.get('block_on_critical')}")
    lines.append(f"  block_on_high_security : {policy.get('block_on_high_security')}")
    lines.append(f"  max_failed_p1_flows    : {policy.get('max_failed_p1_flows')}")
    lines.append(f"  max_flake_rate         : {policy.get('max_flake_rate')}")
    return "\n".join(lines)


def _render_markdown(
    payload: Mapping[str, Any],
    breakdown: Sequence[Mapping[str, Any]],
) -> str:
    total = payload["total"]
    total_repr = "N/A" if total is None else f"{float(total):.2f}"
    parts: list[str] = []
    parts.append(f"# Score explanation for {payload['run_id']}")
    parts.append("")
    parts.append(f"- Total quality score: **{total_repr}**")
    parts.append(f"- Release decision: **{payload['release_decision']}**")
    parts.append("")
    parts.append("## Per-axis contribution")
    parts.append("")
    parts.append("| Axis | Component | Weight | Contribution |")
    parts.append("|---|---:|---:|---:|")
    for row in breakdown:
        parts.append(
            f"| {row['axis']} | {row['component']:.4f} | "
            f"{row['weight']:.4f} | {row['contribution']:.4f} |"
        )
    parts.append("")
    parts.append("## Severity penalties applied")
    parts.append("")
    parts.append("| Severity | Penalty |")
    parts.append("|---|---:|")
    for bucket in ("critical", "high", "medium", "low", "info"):
        applied = float(payload["severity_penalties"].get(bucket, 0.0))
        parts.append(f"| {bucket} | {applied:.4f} |")
    parts.append("")
    parts.append("## Blockers")
    parts.append("")
    blockers: list[str] = list(payload["blockers"])
    if blockers:
        for fid in blockers:
            parts.append(f"- `{fid}`")
    else:
        parts.append("_None._")
    parts.append("")
    parts.append("## Policy thresholds")
    parts.append("")
    policy = payload["policy"]
    parts.append("| Key | Value |")
    parts.append("|---|---|")
    for key in (
        "min_quality_score",
        "block_on_critical",
        "block_on_high_security",
        "max_failed_p1_flows",
        "max_flake_rate",
    ):
        parts.append(f"| `{key}` | {policy.get(key)!r} |")
    parts.append("")
    return "\n".join(parts) + "\n"


__all__ = ["run_report"]
