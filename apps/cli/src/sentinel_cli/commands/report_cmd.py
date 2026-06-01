"""`sentinel report` command (explain + re-render).

introduced ``--explain-score``: read ``score.json``, expand the
math, write ``score-explanation.md``.

adds the broader re-render workflow:

- ``sentinel report --latest`` or ``sentinel report --run-id RUN-...``
 re-renders the report set (run/findings/score/junit/sarif/markdown/html)
 for an existing run by reading the persisted artifacts (no module
 re-execution).
- ``--format`` limits which formats to (re)write.
- ``--open`` opens the HTML in the default browser (skipped in CI mode).

The two paths share argument parsing; ``--explain-score`` continues to
work exactly as it did in.
"""

from __future__ import annotations

import json
import os
import webbrowser
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.quality_score import QualityScore
from engine.domain.target import Target
from engine.domain.test_run import TestRun
from engine.errors.codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INTERNAL_ERROR,
    EXIT_SUCCESS,
)
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.dispatcher import Reporter, ReportInputs
from engine.reporter.slack import render_slack_payload

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

_SUPPORTED_NOTIFY: tuple[str, ...] = ("slack",)

_RERENDER_FORMATS: tuple[str, ...] = (
    "run",
    "findings",
    "score",
    "junit",
    "sarif",
    "markdown",
    "html",
)
_FORMAT_ALIASES: dict[str, tuple[str, ...]] = {
    "json": ("run", "findings", "score"),
    "md": ("markdown",),
}


def run_report(
    ctx: typer.Context,
    explain_score: Annotated[
        bool,
        typer.Option(
            "--explain-score",
            help="Print the math behind score.json (Phase 14).",
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
    format_: Annotated[
        list[str] | None,
        typer.Option(
            "--format",
            help=(
                "Which formats to (re)render: html, json, sarif, junit, md. "
                "Repeat the flag to render multiple. Defaults to all."
            ),
        ),
    ] = None,
    open_in_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Open the rendered HTML report in the default browser (skipped in CI).",
        ),
    ] = False,
    notify: Annotated[
        list[str] | None,
        typer.Option(
            "--notify",
            help=(
                "Push a summary to a downstream channel after re-render. "
                "Repeat to fan out. Currently supported: slack."
            ),
        ),
    ] = None,
) -> None:
    """Re-render reports for a completed run, or explain its score."""

    state: GlobalState = ctx.obj

    try:
        run_dir = _resolve_run_dir(runs_root, run_id=run_id, latest=latest)
    except _ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from None

    if explain_score:
        _run_explain(state, run_dir)
        raise typer.Exit(code=EXIT_SUCCESS)

    formats = _resolve_formats(format_)
    if not formats:
        typer.echo(
            "error: --format produced an empty set; pass at least one of "
            "html, json, sarif, junit, md.",
            err=True,
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)

    try:
        outputs = _rerender(run_dir, formats)
    except _ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_INTERNAL_ERROR) from None

    if state.json:
        with json_stdout() as stream:
            stream.emit(
                {
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir),
                    "formats": sorted(formats),
                    "outputs": {fmt: str(path) for fmt, path in outputs.items()},
                }
            )
    elif not state.quiet:
        typer.echo(f"Re-rendered {len(outputs)} artifact(s) into {run_dir}:")
        for fmt in sorted(outputs):
            typer.echo(f"  {fmt:<10} {outputs[fmt]}")

    if open_in_browser and "html" in outputs:
        if state.ci:
            if not state.quiet:
                typer.echo("--open ignored in CI mode.", err=True)
        else:
            webbrowser.open(outputs["html"].as_uri())

    if notify:
        try:
            _dispatch_notifications(run_dir=run_dir, channels=notify, state=state)
        except _ReportError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=EXIT_CONFIG_ERROR) from None

    raise typer.Exit(code=EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ReportError(Exception):
    """Internal sentinel mapped to the appropriate exit code at the boundary."""


def _resolve_run_dir(
    runs_root: Path,
    *,
    run_id: str | None,
    latest: bool,
) -> Path:
    del latest
    base = runs_root / (run_id if run_id is not None else "latest")
    if not base.exists():
        raise _ReportError(
            f"run directory not found at {base}. Run an audit first or pass --run-id."
        )
    if base.is_symlink() or base.name == "latest":
        target = base.resolve()
        if not target.exists():
            raise _ReportError(f"`latest` pointer at {base} is dangling.")
        return target
    return base


def _resolve_formats(requested: Sequence[str] | None) -> set[str]:
    if not requested:
        return set(_RERENDER_FORMATS)
    expanded: set[str] = set()
    for raw in requested:
        token = raw.strip().lower()
        if not token:
            continue
        if token in _FORMAT_ALIASES:
            expanded.update(_FORMAT_ALIASES[token])
        elif token in _RERENDER_FORMATS:
            expanded.add(token)
    return expanded


def _rerender(run_dir: Path, formats: set[str]) -> dict[str, Path]:
    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        raise _ReportError(f"missing run.json in {run_dir}; cannot re-render.")

    run_payload = _load_json(run_json_path)
    findings = _load_findings(run_dir)
    score = _load_score_obj(run_dir, run_id=str(run_payload["run_id"]))
    policy = _load_policy(run_dir, run_id=str(run_payload["run_id"]))
    module_results = _load_module_results(run_dir)

    run = _build_test_run(run_payload)

    artifact_dir = ArtifactDirectory(run_dir)
    reporter = Reporter()
    inputs = ReportInputs(
        run=run,
        findings=tuple(findings),
        module_results=tuple(module_results),
        score=score,
        policy=policy,
        config_snapshot=run_payload.get("config_snapshot", {})
        if isinstance(run_payload.get("config_snapshot"), dict)
        else {},
        policy_config={},
    )
    # Re-render does NOT write audit-log entries: the audit log is a
    # one-shot record of the original run's safety + module decisions
    # (CLAUDE §11). Adding fresh `artifact_emitted` lines here would
    # both break idempotency (each re-render adds entries) and lie
    # about when the original run made those decisions.
    return reporter.emit(
        inputs,
        artifact_dir,
        sorted(formats),
        audit_log_path=None,
    )


def _build_test_run(payload: Mapping[str, Any]) -> TestRun:
    target_block = payload.get("target", {}) or {}
    base_url = str(target_block.get("base_url", "http://localhost"))
    mode_raw = str(target_block.get("mode", "safe"))
    mode_value = mode_raw if mode_raw in {"safe", "authorized_destructive"} else "safe"
    target = Target(
        base_url=base_url,  # type: ignore[arg-type]
        mode=mode_value,  # type: ignore[arg-type]
    )
    started_at = _parse_iso(str(payload["started_at"]))
    finished_at = _parse_iso(str(payload["finished_at"])) if payload.get("finished_at") else None
    status = str(payload.get("status", "incomplete"))
    modules_run = tuple(sorted(payload.get("modules_run", []) or []))
    return TestRun(
        id=str(payload["run_id"]),
        started_at=started_at,
        finished_at=finished_at,
        target=target,
        config_snapshot=payload.get("config_snapshot", {}) or {},
        modules_run=modules_run,
        status=status,  # type: ignore[arg-type]
    )


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _ReportError(f"could not parse timestamp {value!r}: {exc}") from exc


def _load_findings(run_dir: Path) -> list[Finding]:
    path = run_dir / "findings.json"
    if not path.exists():
        return []
    doc = _load_json(path)
    out: list[Finding] = []
    for entry in doc.get("findings", []):
        if not isinstance(entry, dict):
            continue
        location = FindingLocation()
        loc_block = entry.get("location")
        if isinstance(loc_block, dict):
            location = FindingLocation(
                route=loc_block.get("route"),
                selector=loc_block.get("selector"),
                file=loc_block.get("file"),
                line=loc_block.get("line"),
            )
        evidence: list[Evidence] = []
        for ev in entry.get("evidence", []) or []:
            if not isinstance(ev, dict):
                continue
            ev_type_raw = str(ev.get("type", "trace"))
            evidence.append(
                Evidence(
                    id=str(ev["id"]),
                    type=ev_type_raw,  # type: ignore[arg-type]
                    path=Path(str(ev.get("path", ""))),
                    redacted=bool(ev.get("redacted", True)),
                )
            )
        try:
            created_at = _parse_iso(str(entry.get("created_at")))
        except _ReportError:
            created_at = datetime.now(UTC)
        out.append(
            Finding(
                id=str(entry["id"]),
                run_id=str(entry.get("run_id", "")),
                module=str(entry.get("module", "unknown")),
                category=str(entry.get("category", "general")),
                severity=str(entry.get("severity", "info")),  # type: ignore[arg-type]
                confidence=float(entry.get("confidence", 0.5)),
                title=str(entry.get("title", "Untitled finding")),
                description=str(entry.get("description", "")),
                location=location,
                evidence=tuple(evidence),
                reproduction_steps=tuple(entry.get("reproduction_steps", []) or []),
                recommendation=str(entry.get("recommendation", "")),
                suggested_fix=entry.get("suggested_fix"),
                affected_target=entry.get("affected_target"),
                created_at=created_at,
            )
        )
    return out


def _load_score_obj(run_dir: Path, *, run_id: str) -> QualityScore | None:
    path = run_dir / "score.json"
    if not path.exists():
        return None
    payload = _load_json(path)
    total = payload.get("total")
    if total is None:
        return None
    return QualityScore(
        id="SCR-RERENDERAAAA",
        run_id=run_id,
        total=float(total),
        components=dict(payload.get("components", {})),
        weights=dict(payload.get("weights", {})),
        severity_penalties_applied=dict(payload.get("severity_penalties", {})),
    )


def _load_policy(run_dir: Path, *, run_id: str) -> PolicyDecision | None:
    path = run_dir / "score.json"
    if not path.exists():
        return None
    payload = _load_json(path)
    decision = payload.get("release_decision")
    if not decision:
        return None
    return PolicyDecision(
        id="PD-RERENDERAAAA",
        run_id=run_id,
        release_decision=str(decision),  # type: ignore[arg-type]
        blocked_by=tuple(payload.get("blockers", []) or []),
        reasons=tuple(payload.get("reasons", []) or []),
    )


def _load_module_results(run_dir: Path) -> list[ModuleResult]:
    out: list[ModuleResult] = []
    module_dir = run_dir / "module-results"
    if not module_dir.is_dir():
        return out
    for path in sorted(module_dir.glob("*.json")):
        try:
            payload = _load_json(path)
        except _ReportError:
            continue
        stem = path.stem.upper()
        fallback_id = f"MOD-{stem[:12].ljust(12, 'A')}"
        out.append(
            ModuleResult(
                id=str(payload.get("id", fallback_id)),
                name=str(payload.get("name", path.stem)),
                status=str(payload.get("status", "incomplete")),  # type: ignore[arg-type]
                findings=tuple(payload.get("findings", []) or []),
                metrics=dict(payload.get("metrics", {})),
                duration_ms=int(payload.get("duration_ms", 0)),
                errors=tuple(payload.get("errors", []) or []),
            )
        )
    return out


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _ReportError(f"could not parse {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise _ReportError(f"{path} did not contain a JSON object.")
    return payload


# ---------------------------------------------------------------------------
# Explain (path)
# ---------------------------------------------------------------------------


def _run_explain(state: GlobalState, run_dir: Path) -> None:
    score_path = run_dir / "score.json"
    if not score_path.exists():
        typer.echo(
            f"error: score.json not found at {score_path}. Run a non-dry-run audit first.",
            err=True,
        )
        raise typer.Exit(code=EXIT_CONFIG_ERROR)
    try:
        payload = _load_score_for_explain(score_path)
    except _ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_CONFIG_ERROR) from None
    breakdown = _build_breakdown(payload)
    markdown = _render_explain_markdown(payload, breakdown)
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
        typer.echo(_render_explain_human(payload, breakdown))
        typer.echo(f"\nWrote {explanation_path}")


def _load_score_for_explain(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
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
            raise _ReportError(f"score.json is missing required key {key!r}.")
    return payload


def _build_breakdown(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
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


def _render_explain_human(
    payload: Mapping[str, Any], breakdown: Sequence[Mapping[str, Any]]
) -> str:
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


def _render_explain_markdown(
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


def _dispatch_notifications(
    *,
    run_dir: Path,
    channels: Sequence[str],
    state: GlobalState,
) -> None:
    """Push the re-rendered summary out via each requested notifier.

    : only ``slack`` is wired. Unknown channels raise
    ``_ReportError`` so the caller can surface exit-code 2.
    """

    for raw in channels:
        channel = raw.strip().lower()
        if not channel:
            continue
        if channel not in _SUPPORTED_NOTIFY:
            raise _ReportError(
                f"--notify channel {raw!r} is not supported. "
                f"Choose one of: {', '.join(_SUPPORTED_NOTIFY)}."
            )
        if channel == "slack":
            _dispatch_slack(run_dir=run_dir, state=state)


def _dispatch_slack(*, run_dir: Path, state: GlobalState) -> None:
    from integrations.slack import SLACK_WEBHOOK_ENV, post_payload

    webhook = os.environ.get(SLACK_WEBHOOK_ENV, "").strip()
    if not webhook:
        raise _ReportError(
            f"--notify slack: env var {SLACK_WEBHOOK_ENV!r} is unset; " f"refusing to post."
        )

    run_payload = _load_json(run_dir / "run.json")
    run = _build_test_run(run_payload)
    findings = _load_findings(run_dir)
    score = _load_score_obj(run_dir, run_id=str(run_payload["run_id"]))
    policy = _load_policy(run_dir, run_id=str(run_payload["run_id"]))
    payload = render_slack_payload(run, findings, score, policy)

    dedup_path = run_dir / "slack-dedup.json"
    reply = post_payload(
        payload=payload,
        webhook_url=webhook,
        dedup_path=dedup_path,
    )
    if not state.json and not state.quiet:
        typer.echo(f"  notify(slack) -> {reply or 'ok'}")


__all__ = ["run_report"]
