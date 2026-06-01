"""GitHub PR comment generator (Phase 15, task 15.02).

Produces a GitHub-flavored Markdown comment summarizing a run. The
output is sized to fit GitHub's 65 535-character comment limit and
includes an upsert anchor (``<!-- sentinelqa:pr-comment -->``) so the
GitHub Action (Phase 17) can edit the same comment on subsequent runs
rather than spawning new ones.

Style discipline:

- All user-controlled strings flow through
  :func:`engine.reporter.markdown_writer.md_escape` so a malicious
  finding title cannot inject Markdown or HTML.
- Output is deterministic: sort orders are fixed and the trailing
  newline is normalized so byte-for-byte goldens hold.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from engine.domain.finding import Finding, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.reporter.markdown_writer import (
    RELEASE_DECISION_LABEL,
    SEVERITY_LABEL,
    SEVERITY_ORDER,
    md_escape,
)

PR_COMMENT_ANCHOR: Final[str] = "<!-- sentinelqa:pr-comment -->"
"""HTML-comment anchor used by the Phase 17 Action to upsert the comment."""

PR_COMMENT_MAX_CHARS: Final[int] = 65_535
"""GitHub's per-comment character limit."""

_CRITICAL_TOP_N: Final[int] = 5


def render_pr_comment(
    run: TestRun,
    findings: Sequence[Finding],
    score: QualityScore | None,
    policy: PolicyDecision | None,
    *,
    module_results: Sequence[ModuleResult] = (),
    changed_flows: Sequence[str] = (),
    artifact_url: str | None = None,
) -> str:
    """Render a PR-comment Markdown body.

    Always begins with :data:`PR_COMMENT_ANCHOR` so the upsert flow can
    find existing comments. The trailing newline is always present so
    GitHub renders the final list item without truncation.
    """

    release_decision = _derive_release_decision(run, policy)
    score_display = _score_display(run, score)
    counts = _severity_counts(findings)

    blocking_findings = [f for f in findings if f.severity in {"critical", "high"}]
    blocking_findings.sort(key=lambda f: (SEVERITY_ORDER.index(f.severity), f.id))
    blocking_top = blocking_findings[:_CRITICAL_TOP_N]

    lines: list[str] = [PR_COMMENT_ANCHOR, ""]
    lines.extend(_render_header(run, release_decision, score_display))
    lines.append("")
    lines.extend(_render_decision_section(policy, release_decision, score_display))
    lines.append("")
    lines.extend(_render_critical_section(blocking_top, blocking_findings))
    lines.append("")
    lines.extend(_render_changed_flows(changed_flows))
    lines.append("")
    lines.extend(_render_module_summary(module_results, findings))
    lines.append("")
    lines.extend(_render_llm_audit_section(findings))
    lines.append("")
    lines.extend(_render_artifacts(artifact_url))
    lines.append("")
    lines.extend(_render_next_steps(release_decision, counts))
    body = "\n".join(lines).rstrip() + "\n"

    if len(body) > PR_COMMENT_MAX_CHARS:
        body = _truncate_body(body)
    return body


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_header(
    run: TestRun,
    release_decision: ReleaseDecision,
    score_display: str,
) -> list[str]:
    return [
        f"## SentinelQA — {md_escape(run.id)}",
        "",
        f"- **Release decision:** {RELEASE_DECISION_LABEL[release_decision]}",
        f"- **Quality score:** {score_display}",
        f"- **Target:** `{md_escape(str(run.target.base_url))}`",
        f"- **Status:** `{md_escape(run.status)}`",
    ]


def _render_decision_section(
    policy: PolicyDecision | None,
    release_decision: ReleaseDecision,
    score_display: str,
) -> list[str]:
    out = ["### Decision rationale", ""]
    if policy is None:
        out.append(f"_Derived from run status `{release_decision}`; " f"score {score_display}._")
        return out
    if policy.blocked_by:
        out.append("**Blocked by:**")
        for blocker_id in policy.blocked_by:
            out.append(f"- `{md_escape(blocker_id)}`")
    if policy.reasons:
        out.append("")
        out.append("**Reasons:**")
        for reason in policy.reasons:
            out.append(f"- {md_escape(reason)}")
    if not policy.blocked_by and not policy.reasons:
        out.append("_All policy gates green._")
    return out


def _render_critical_section(
    top: Sequence[Finding],
    all_blocking: Sequence[Finding],
) -> list[str]:
    out = ["### Critical findings", ""]
    if not all_blocking:
        out.append("_No critical or high-severity findings._")
        return out
    out.append("| Severity | Module | Title | ID |")
    out.append("|---|---|---|---|")
    for f in top:
        out.append(
            f"| {SEVERITY_LABEL[f.severity]} "
            f"| `{md_escape(f.module)}` "
            f"| {md_escape(f.title)} "
            f"| `{md_escape(f.id)}` |"
        )
    if len(all_blocking) > len(top):
        remaining = len(all_blocking) - len(top)
        out.append("")
        out.append(f"_+{remaining} more in the full report._")
    return out


def _render_changed_flows(changed_flows: Sequence[str]) -> list[str]:
    out = ["### Changed flows tested", ""]
    if not changed_flows:
        out.append("_Diff-aware mode was not used for this run._")
        return out
    for flow in changed_flows:
        out.append(f"- `{md_escape(flow)}`")
    return out


def _render_module_summary(
    module_results: Sequence[ModuleResult],
    findings: Sequence[Finding],
) -> list[str]:
    out = ["### Module summary", ""]
    if not module_results:
        out.append("_No module results recorded._")
        return out
    counts_by_module: dict[str, int] = {}
    for f in findings:
        counts_by_module[f.module] = counts_by_module.get(f.module, 0) + 1
    out.append("| Module | Status | Findings | Duration |")
    out.append("|---|---|---|---|")
    for m in sorted(module_results, key=lambda mr: mr.name):
        out.append(
            f"| `{md_escape(m.name)}` "
            f"| `{md_escape(m.status)}` "
            f"| {counts_by_module.get(m.name, 0)} "
            f"| {m.duration_ms} ms |"
        )
    return out


def _render_llm_audit_section(findings: Sequence[Finding]) -> list[str]:
    """Highlight LLM-Code audit findings — SentinelQA's marketing differentiator.

    Renders only when at least one ``llm_audit`` finding is present so
    clean runs don't litter PR comments with empty sections.
    """

    llm_findings = [f for f in findings if f.module == "llm_audit"]
    if not llm_findings:
        return []
    by_category: dict[str, list[Finding]] = {}
    for f in llm_findings:
        by_category.setdefault(f.category, []).append(f)
    out = ["### LLM-Code Audit", ""]
    out.append("Detected defects characteristic of LLM-generated code (the documentation).")
    out.append("")
    out.append("| Category | Findings | Highest severity |")
    out.append("|---|---|---|")
    for category in sorted(by_category):
        bucket = by_category[category]
        severities = {f.severity for f in bucket}
        highest: Severity = next(
            (s for s in SEVERITY_ORDER if s in severities),
            "info",
        )
        out.append(f"| `{md_escape(category)}` | {len(bucket)} | {SEVERITY_LABEL[highest]} |")
    return out


def _render_artifacts(artifact_url: str | None) -> list[str]:
    out = ["### Artifacts", ""]
    if artifact_url:
        out.append(f"- [Full report bundle]({_md_link(artifact_url)})")
    else:
        out.append("- _Upload the run artifacts to view the full HTML / SARIF report._")
    return out


def _render_next_steps(
    release_decision: ReleaseDecision,
    counts: Mapping[Severity, int],
) -> list[str]:
    out = ["### Suggested next steps", ""]
    if release_decision == "blocked":
        out.append("- Review every blocker above and fix or downgrade with rationale.")
        out.append("- Re-run `sentinel ci` once fixes land.")
    elif release_decision == "pass_with_warnings":
        out.append("- Triage medium / low findings; merge if accepted.")
    elif release_decision == "unsafe_target_rejected":
        out.append("- Confirm the target is authorized and within the safety policy.")
    elif release_decision == "inconclusive":
        out.append("- Re-run with the full module set to obtain a decision.")
    else:
        out.append("- Ship it. Optional: open follow-ups for info findings.")
    if counts.get("medium", 0) or counts.get("low", 0):
        out.append("- See `report.html` for the full breakdown.")
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_release_decision(run: TestRun, policy: PolicyDecision | None) -> ReleaseDecision:
    if policy is not None:
        return policy.release_decision
    if run.status == "unsafe_blocked":
        return "unsafe_target_rejected"
    if run.status == "dry_run":
        return "inconclusive"
    if run.status == "passed":
        return "pass"
    if run.status == "failed":
        return "blocked"
    return "inconclusive"


def _score_display(run: TestRun, score: QualityScore | None) -> str:
    if score is None or run.status in {"unsafe_blocked", "dry_run"}:
        return "n/a"
    return f"{round(float(score.total), 2)} / 100"


def _severity_counts(findings: Sequence[Finding]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _md_link(target: str) -> str:
    return target.replace("(", "%28").replace(")", "%29")


def _truncate_body(body: str) -> str:
    """Cap ``body`` at :data:`PR_COMMENT_MAX_CHARS` with a notice."""

    notice = "\n\n_Report truncated to fit GitHub's comment limit. See `report.html`._\n"
    keep = PR_COMMENT_MAX_CHARS - len(notice)
    return body[:keep] + notice


__all__ = [
    "PR_COMMENT_ANCHOR",
    "PR_COMMENT_MAX_CHARS",
    "render_pr_comment",
]
