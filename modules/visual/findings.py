"""Translate :class:`DiffOutcome` records into typed Findings."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.visual.models import DiffOutcome

# Per-status finding category + severity (matches PRD §18.2 wire format).
_CATEGORY = {
    "differ": "visual_pixel_diff",
    "size_mismatch": "visual_size_mismatch",
    "missing_current": "visual_missing_current",
}
_SEVERITY: dict[str, Severity] = {
    "differ": "medium",
    "size_mismatch": "high",
    "missing_current": "medium",
}


def _describe(outcome: DiffOutcome) -> str:
    if outcome.status == "differ":
        return (
            f"Visual diff exceeded threshold for {outcome.route_slug!r} "
            f"at viewport {outcome.viewport!r}. "
            f"{outcome.differing_pixels} of {outcome.total_pixels} pixels differ "
            f"({outcome.diff_fraction:.4f} vs threshold {outcome.threshold:.4f})."
            + (
                f" SSIM={outcome.ssim:.4f}" f" (min={outcome.min_similarity:.4f})."
                if outcome.ssim is not None and outcome.min_similarity is not None
                else ""
            )
        )
    if outcome.status == "size_mismatch":
        return (
            f"Visual size mismatch for {outcome.route_slug!r} at viewport "
            f"{outcome.viewport!r}. Baseline vs current differ in pixel "
            "dimensions; capture or viewport drift is the most common cause."
        )
    if outcome.status == "missing_current":
        return (
            f"Baseline exists for {outcome.route_slug!r} at viewport "
            f"{outcome.viewport!r} but the current run captured no PNG. "
            "The capture step skipped this route or the file path was wrong."
        )
    return f"Visual outcome with unexpected status {outcome.status!r}."


def _recommendation(outcome: DiffOutcome) -> str:
    if outcome.status == "size_mismatch":
        return (
            "Re-capture this route at the configured viewport size, OR "
            "if the change is intentional, accept the new baseline locally "
            "via `sentinel visual accept` and commit the updated PNG."
        )
    if outcome.status == "missing_current":
        return (
            "Verify the capture step ran for this viewport; the route may "
            "be unreachable from the configured target. Re-run "
            "`sentinel visual capture` and inspect the run's visual log."
        )
    return (
        "Review the diff overlay; if the change is expected, accept the "
        "new baseline locally via `sentinel visual accept`. Otherwise the "
        "app changed visually under the configured viewport."
    )


def _evidence_paths(outcome: DiffOutcome, *, run_dir: Path) -> tuple[str, ...]:
    """Return relative POSIX evidence paths anchored at the run dir."""

    paths: list[str] = []
    for candidate in (outcome.baseline_path, outcome.current_path, outcome.diff_path):
        if candidate is None:
            continue
        try:
            rel = candidate.resolve().relative_to(run_dir.resolve())
        except ValueError:
            rel = candidate
        paths.append(str(rel).replace("\\", "/"))
    if not paths:
        paths.append("visual/index.json")
    return tuple(paths)


def findings_from_diffs(
    outcomes: Iterable[DiffOutcome],
    *,
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    run_dir: Path,
) -> tuple[Finding, ...]:
    """Translate diff outcomes into typed :class:`Finding` records.

    ``match`` and ``missing_baseline`` outcomes are silently skipped:
    they are not findings (the former is the happy path, the latter is
    the operator's signal to run ``sentinel visual accept``).
    """

    now = datetime.now(UTC)
    findings: list[Finding] = []
    for outcome in outcomes:
        if not outcome.is_finding:
            continue
        if outcome.status not in _CATEGORY:
            continue
        category = _CATEGORY[outcome.status]
        severity = _SEVERITY[outcome.status]
        confidence = 0.95 if outcome.status == "size_mismatch" else 0.9
        evidence_paths = _evidence_paths(outcome, run_dir=run_dir)
        evidence = tuple(
            Evidence(
                id=id_generator.new("EVD"),
                type="screenshot",
                path=Path(p),
            )
            for p in evidence_paths
        )
        title = (
            f"Visual regression: {outcome.route_slug} @ {outcome.viewport}"
            if outcome.status != "missing_current"
            else f"Visual capture missing: {outcome.route_slug} @ {outcome.viewport}"
        )
        location = FindingLocation(route=outcome.route_slug)
        findings.append(
            Finding(
                id=id_generator.new("FND"),
                run_id=run_id,
                module="visual",
                category=category,
                severity=severity,
                confidence=confidence,
                title=title,
                description=_describe(outcome),
                location=location,
                evidence=evidence,
                reproduction_steps=(
                    "Re-run `sentinel visual diff` against the current target.",
                    f"Open the diff overlay PNG at {outcome.diff_path}."
                    if outcome.diff_path is not None
                    else "Open the run's visual/ artifact directory.",
                ),
                affected_target=target_base_url,
                recommendation=_recommendation(outcome),
                created_at=now,
            )
        )
    return tuple(findings)


__all__ = ["findings_from_diffs"]
