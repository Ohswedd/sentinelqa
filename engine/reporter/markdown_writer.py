"""Markdown report (`report.md`, task 03.06).

A concise Markdown summary optimized for PR comments and quick scans
(PRD §21.2). The full HTML report lands in Phase 15. Style rules:

- Deterministic ordering: findings sorted by severity (critical → info)
  then by id; modules sorted alphabetically.
- All user-controlled fields are escaped via :func:`md_escape` so a
  malicious finding title cannot inject Markdown / HTML.
- Headers fixed; tables use the same column widths every time so byte
  comparisons hold across runs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from engine.domain.finding import Finding, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory

# Order findings + summary sections from most-severe to least.
SEVERITY_ORDER: Final[tuple[Severity, ...]] = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
)

# Severity → emoji marker. Plain ASCII fallback chosen so PR comments
# render correctly even when emoji rendering is disabled. PRs render
# the unicode anyway; the wrappers stay short to keep tables tight.
SEVERITY_LABEL: Final[Mapping[Severity, str]] = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}

# Release decision → short status line. Plain text only; PR-comment
# friendly without depending on color emoji rendering.
RELEASE_DECISION_LABEL: Final[Mapping[ReleaseDecision, str]] = {
    "pass": "PASS",
    "pass_with_warnings": "PASS (with warnings)",
    "blocked": "BLOCKED",
    "inconclusive": "INCONCLUSIVE",
    "unsafe_target_rejected": "UNSAFE TARGET — BLOCKED",
}


def write_markdown(
    artifact_dir: ArtifactDirectory,
    run: TestRun,
    *,
    findings: Sequence[Finding] = (),
    module_results: Sequence[ModuleResult] = (),
    score: QualityScore | None = None,
    policy: PolicyDecision | None = None,
    html_report_path: str | None = "report.html",
    filename: str = "report.md",
) -> Path:
    """Render and persist `report.md`. Returns the written path."""

    body = render_markdown(
        run,
        findings=findings,
        module_results=module_results,
        score=score,
        policy=policy,
        html_report_path=html_report_path,
    )
    return artifact_dir.write_text(filename, body)


def render_markdown(
    run: TestRun,
    *,
    findings: Sequence[Finding] = (),
    module_results: Sequence[ModuleResult] = (),
    score: QualityScore | None = None,
    policy: PolicyDecision | None = None,
    html_report_path: str | None = "report.html",
) -> str:
    """Render the Markdown document as a string (no I/O)."""

    release_decision: ReleaseDecision
    if policy is not None:
        release_decision = policy.release_decision
    elif run.status == "unsafe_blocked":
        release_decision = "unsafe_target_rejected"
    elif run.status == "dry_run":
        release_decision = "inconclusive"
    elif run.status == "passed":
        release_decision = "pass"
    elif run.status == "failed":
        release_decision = "blocked"
    else:
        release_decision = "inconclusive"

    score_value = score.total if score is not None else None
    if run.status in {"unsafe_blocked", "dry_run"}:
        score_value = None

    lines: list[str] = []
    lines.extend(_render_title(run, release_decision, score_value))
    lines.append("")
    lines.extend(_render_summary(run, module_results, findings))
    lines.append("")
    lines.extend(_render_findings_section(findings))
    lines.append("")
    lines.extend(_render_modules_table(module_results, findings))
    lines.append("")
    lines.extend(_render_footer(html_report_path))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_title(
    run: TestRun,
    release_decision: ReleaseDecision,
    score_value: float | None,
) -> list[str]:
    quality_str = "n/a" if score_value is None else f"{round(float(score_value), 2)} / 100"
    return [
        f"# SentinelQA Report — {md_escape(run.id)}",
        "",
        f"**Release decision:** {RELEASE_DECISION_LABEL[release_decision]}  ",
        f"**Quality score:** {quality_str}",
    ]


def _render_summary(
    run: TestRun,
    module_results: Sequence[ModuleResult],
    findings: Sequence[Finding],
) -> list[str]:
    duration_s: str
    if run.finished_at is not None:
        delta = (run.finished_at - run.started_at).total_seconds()
        duration_s = f"{delta:.1f}s"
    else:
        duration_s = "n/a"

    parsed = urlparse(str(run.target.base_url))
    target_display = parsed.geturl()

    modules = sorted({m.name for m in module_results} | set(run.modules_run))
    module_list = ", ".join(f"`{md_escape(m)}`" for m in modules) if modules else "_(none)_"

    counts = _severity_counts(findings)
    counts_str = ", ".join(
        f"{counts[s]} {SEVERITY_LABEL[s].lower()}" for s in SEVERITY_ORDER if counts.get(s, 0) > 0
    )
    counts_str = counts_str or "0 findings"

    return [
        "## Summary",
        "",
        f"- Run ID: `{md_escape(run.id)}`",
        f"- Target: `{md_escape(target_display)}` (mode: `{md_escape(run.target.mode)}`)",
        f"- Status: `{md_escape(run.status)}`",
        f"- Duration: {duration_s}",
        f"- Modules: {module_list}",
        f"- Findings: {counts_str}",
    ]


def _render_findings_section(findings: Sequence[Finding]) -> list[str]:
    blocking = [f for f in findings if f.severity in {"critical", "high"}]
    blocking.sort(key=lambda f: (SEVERITY_ORDER.index(f.severity), f.id))

    out: list[str] = ["## Critical & high-severity findings", ""]
    if not blocking:
        out.append("_No critical or high findings reported._")
        return out
    for f in blocking:
        evidence_links = ", ".join(
            f"[{md_escape(ev.type)}]({_md_link(str(ev.path))})" for ev in f.evidence
        )
        suffix = f" — Evidence: {evidence_links}" if evidence_links else ""
        out.append(
            f"- `{md_escape(f.id)}` — **{SEVERITY_LABEL[f.severity]}: "
            f"{md_escape(f.title)}**{suffix}"
        )
    return out


def _render_modules_table(
    module_results: Sequence[ModuleResult],
    findings: Sequence[Finding],
) -> list[str]:
    if not module_results:
        return ["## Per-module results", "", "_No module results recorded for this run._"]

    counts_by_module: dict[str, int] = {}
    for f in findings:
        counts_by_module[f.module] = counts_by_module.get(f.module, 0) + 1

    rows = []
    for m in sorted(module_results, key=lambda mr: mr.name):
        rows.append(
            f"| `{md_escape(m.name)}` "
            f"| `{md_escape(m.status)}` "
            f"| {counts_by_module.get(m.name, 0)} "
            f"| {m.duration_ms} ms |"
        )

    return [
        "## Per-module results",
        "",
        "| Module | Status | Findings | Duration |",
        "|---|---|---|---|",
        *rows,
    ]


def _render_footer(html_report_path: str | None) -> list[str]:
    lines = ["## Artifacts", ""]
    if html_report_path:
        lines.append(
            f"- HTML report: [`{md_escape(html_report_path)}`]"
            f"({_md_link(html_report_path)}) _(generated in Phase 15)_"
        )
    lines.append("- Traces, screenshots, and audit log live next to this report.")
    return lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MD_ESCAPE_CHARS: Final[str] = r"\`*_{}[]()#+-.!|<>"


def md_escape(value: str) -> str:
    """Backslash-escape Markdown control characters in ``value``.

    Defends against injection via finding titles / descriptions / module
    names (CLAUDE.md §32). Pipe (`|`) is included so table cells stay
    well-formed even with arbitrary user input.
    """

    out: list[str] = []
    for ch in str(value):
        if ch in _MD_ESCAPE_CHARS:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def _md_link(target: str) -> str:
    """Escape parentheses inside a link target."""

    return target.replace("(", "%28").replace(")", "%29")


def _severity_counts(findings: Sequence[Finding]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


__all__ = [
    "RELEASE_DECISION_LABEL",
    "SEVERITY_LABEL",
    "SEVERITY_ORDER",
    "md_escape",
    "render_markdown",
    "write_markdown",
]
