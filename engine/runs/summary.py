# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Read a run directory and produce a normalised :class:`RunSummary`.

Used by ``sentinel ask``, ``sentinel.compare_runs``, the report
explainer, and the post-run flake DB hook. The summary intentionally
flattens the wire format: one tuple of findings, one score tuple,
one set of modules-run. Missing files yield empty defaults rather
than raising, so callers can degrade gracefully on partial runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FindingRef:
    """One row in :attr:`RunSummary.findings`."""

    id: str
    module: str
    category: str
    severity: str
    title: str
    code: str = ""  # e.g. ``SEC-HEADERS-CSP-MISSING``


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Normalised view of one run directory."""

    run_id: str
    status: str
    quality_score: float | None
    modules_run: tuple[str, ...]
    findings: tuple[FindingRef, ...]
    target_base_url: str = ""
    target_host: str = ""
    started_at: str = ""
    finished_at: str | None = None
    summary_counts: dict[str, int] = field(default_factory=dict)
    raw_run_json: dict[str, Any] = field(default_factory=dict)
    raw_findings_json: dict[str, Any] = field(default_factory=dict)
    raw_score_json: dict[str, Any] = field(default_factory=dict)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalise_findings(payload: dict[str, Any]) -> tuple[FindingRef, ...]:
    rows = payload.get("findings")
    if not isinstance(rows, list):
        return ()
    out: list[FindingRef] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Pull a stable rule-code from common locations.
        code = ""
        evidence = row.get("evidence")
        if isinstance(evidence, dict):
            for key in ("rule_id", "code", "check"):
                value = evidence.get(key)
                if isinstance(value, str) and value:
                    code = value
                    break
        if not code:
            cwe = row.get("cwe_id")
            if isinstance(cwe, str):
                code = cwe
        out.append(
            FindingRef(
                id=str(row.get("id", "")),
                module=str(row.get("module", "")),
                category=str(row.get("category", "")),
                severity=str(row.get("severity", "info")),
                title=str(row.get("title", "")),
                code=code,
            )
        )
    return tuple(out)


def load_run_summary(run_dir: Path) -> RunSummary:
    """Parse ``run.json`` + ``findings.json`` + ``score.json`` from a dir."""

    run_payload = _load_json(run_dir / "run.json")
    findings_payload = _load_json(run_dir / "findings.json")
    score_payload = _load_json(run_dir / "score.json")

    target = run_payload.get("target") or {}
    quality = run_payload.get("quality_score")
    summary_counts_raw = run_payload.get("summary") or {}
    summary_counts: dict[str, int] = {
        k: int(v) for k, v in summary_counts_raw.items() if isinstance(v, int | float)
    }

    return RunSummary(
        run_id=str(run_payload.get("run_id", run_dir.name)),
        status=str(run_payload.get("status", "")),
        quality_score=float(quality) if isinstance(quality, int | float) else None,
        modules_run=tuple(sorted(str(m) for m in (run_payload.get("modules_run") or []))),
        findings=_normalise_findings(findings_payload),
        target_base_url=str(target.get("base_url", "")),
        target_host=str(target.get("host", "")),
        started_at=str(run_payload.get("started_at", "")),
        finished_at=run_payload.get("finished_at"),
        summary_counts=summary_counts,
        raw_run_json=run_payload,
        raw_findings_json=findings_payload,
        raw_score_json=score_payload,
    )


def severity_breakdown(summary: RunSummary) -> dict[str, int]:
    """Return ``{severity: count}`` derived from the findings list."""

    out: dict[str, int] = {}
    for finding in summary.findings:
        out[finding.severity] = out.get(finding.severity, 0) + 1
    return out


__all__ = [
    "FindingRef",
    "RunSummary",
    "load_run_summary",
    "severity_breakdown",
]
