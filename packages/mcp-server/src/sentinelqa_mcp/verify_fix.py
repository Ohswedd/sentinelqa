"""``sentinel.verify_fix`` loop logic (ADR-0023 §verify_fix, task 18.04).

The MCP tool does NOT apply code changes — the agent did that already.
This module:

1. Loads the prior run's persisted ``findings.json``.
2. Runs the canonical audit again against the same URL (so the
   findings are produced against the current working tree).
3. Diffs new findings vs prior findings using a stable fingerprint
   (``module``-``category``-``title``-``location.file``-``location.selector``).
4. Returns :class:`VerifyFixResult` with the four-valued decision
   defined in ADR-0023.

The decision matrix is deterministic. No model calls; no heuristics
beyond the fingerprint set algebra.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sentinelqa import AuditResult, Sentinel


Decision = Literal["fix_verified", "partial", "regressed", "still_failing"]


@dataclass(frozen=True)
class VerifyFixResult:
    """Outcome of one verify-fix loop iteration (ADR-0023)."""

    decision: Decision
    target_finding_id: str | None
    new_run_id: str
    fixed_finding_ids: tuple[str, ...]
    unchanged_finding_ids: tuple[str, ...]
    regression_finding_ids: tuple[str, ...]
    summary: str


def _finding_fingerprint(finding: Mapping[str, Any]) -> str:
    """Stable identity for a finding across runs.

    Uses module / category / title / file / selector — every field that
    is part of the writer's deterministic ordering (Phase 03). Skips
    the per-run ID and timestamps.
    """

    location = finding.get("location") or {}
    parts = (
        str(finding.get("module", "")),
        str(finding.get("category", "")),
        str(finding.get("title", "")),
        str(location.get("file") or ""),
        str(location.get("selector") or ""),
    )
    return "|".join(parts)


def _load_prior_findings(run_dir: Path) -> tuple[Mapping[str, Any], ...]:
    findings_path = run_dir / "findings.json"
    if not findings_path.is_file():
        return ()
    document = json.loads(findings_path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        return ()
    items = document.get("findings", [])
    if not isinstance(items, list):
        return ()
    return tuple(item for item in items if isinstance(item, Mapping))


def _findings_to_payloads(result: AuditResult) -> tuple[Mapping[str, Any], ...]:
    return tuple(f.to_agent_message() for f in result.findings)


def _decide(
    *,
    target_finding_id: str | None,
    target_fingerprint: str | None,
    prior_fingerprints: set[str],
    new_fingerprints: set[str],
) -> tuple[Decision, str]:
    unchanged = prior_fingerprints & new_fingerprints
    new_regressions = new_fingerprints - prior_fingerprints
    has_target = target_fingerprint is not None
    target_still_present = bool(
        target_fingerprint is not None and target_fingerprint in new_fingerprints
    )

    # `fix_verified` requires zero findings in the new run — anything else
    # is partial at best. This is the strictest read of ADR-0023's
    # "AND no new findings appeared" — a release-confidence engine should
    # not call a build "verified" when other failures persist.
    if has_target and target_still_present and new_regressions:
        return ("regressed", "Target finding still present AND new findings appeared.")
    if has_target and target_still_present:
        return ("still_failing", "Target finding still present; no regressions.")
    if has_target and not target_still_present and not new_fingerprints:
        return ("fix_verified", "Target finding cleared and no new findings appeared.")
    if has_target and not target_still_present and new_regressions:
        return ("partial", "Target cleared but new regressions appeared.")
    if has_target and not target_still_present and unchanged:
        return ("partial", "Target cleared but other prior findings linger.")
    if not has_target and not new_fingerprints:
        return ("fix_verified", "No prior target; no findings in the new run.")
    if not has_target and new_regressions:
        return ("partial", "No prior target; new findings appeared.")
    return ("partial", "Indeterminate outcome — see fixed/unchanged/regression sets.")


def _fingerprint_to_id(items: tuple[Mapping[str, Any], ...], fingerprints: set[str]) -> list[str]:
    return [
        str(item.get("id"))
        for item in items
        if _finding_fingerprint(item) in fingerprints and item.get("id")
    ]


async def run_verify_fix(
    *,
    sentinel: Sentinel,
    run_id: str,
    target_finding_id: str | None,
    url: str | None = None,
    modules: tuple[str, ...] | None = None,
) -> VerifyFixResult:
    """Execute one verify-fix loop and return the result.

    ``url`` defaults to the prior run's ``target.base_url`` — the audit
    re-runs against the same target. ``modules`` defaults to whichever
    modules ran in the prior audit so we never broaden the scope
    silently (CLAUDE.md §10).
    """

    prior_run_dir = await sentinel.async_report(run_id=run_id, latest=False)
    prior_findings = _load_prior_findings(prior_run_dir)
    target_fingerprint: str | None = None
    if target_finding_id is not None:
        for item in prior_findings:
            if item.get("id") == target_finding_id:
                target_fingerprint = _finding_fingerprint(item)
                break

    if url is None:
        run_json = prior_run_dir / "run.json"
        if run_json.is_file():
            doc = json.loads(run_json.read_text(encoding="utf-8"))
            target = doc.get("target") or {}
            base = target.get("base_url")
            if isinstance(base, str) and base:
                url = base

    new_result = await sentinel.async_audit(
        url=url,
        modules=modules,
    )
    new_findings = _findings_to_payloads(new_result)

    prior_fps = {_finding_fingerprint(f) for f in prior_findings}
    new_fps = {_finding_fingerprint(f) for f in new_findings}

    decision, summary = _decide(
        target_finding_id=target_finding_id,
        target_fingerprint=target_fingerprint,
        prior_fingerprints=prior_fps,
        new_fingerprints=new_fps,
    )

    fixed_ids = _fingerprint_to_id(prior_findings, prior_fps - new_fps)
    unchanged_ids = _fingerprint_to_id(new_findings, prior_fps & new_fps)
    regression_ids = _fingerprint_to_id(new_findings, new_fps - prior_fps)

    return VerifyFixResult(
        decision=decision,
        target_finding_id=target_finding_id,
        new_run_id=new_result.run_id,
        fixed_finding_ids=tuple(fixed_ids),
        unchanged_finding_ids=tuple(unchanged_ids),
        regression_finding_ids=tuple(regression_ids),
        summary=summary,
    )


__all__ = [
    "Decision",
    "VerifyFixResult",
    "run_verify_fix",
]
