# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Normalised metrics extracted from a completed run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """The shape every metrics adapter consumes."""

    run_id: str
    status: str
    quality_score: float | None
    target_host: str
    started_at: str  # ISO-8601
    duration_ms: int
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    module_durations_ms: dict[str, int] = field(default_factory=dict)
    flake_rate: float | None = None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_duration_ms(payload: dict[str, Any]) -> int:
    """Compute the run duration from started_at/finished_at when available."""

    started = payload.get("started_at")
    finished = payload.get("finished_at")
    if not (isinstance(started, str) and isinstance(finished, str)):
        return 0
    from datetime import datetime

    try:
        delta = datetime.fromisoformat(finished) - datetime.fromisoformat(started)
        return max(int(delta.total_seconds() * 1000), 0)
    except ValueError:
        return 0


def extract_run_metrics(run_dir: Path) -> RunMetrics:
    """Walk a run dir and return :class:`RunMetrics`."""

    run_payload = _load_json(run_dir / "run.json")
    findings_payload = _load_json(run_dir / "findings.json")

    severity_counts: dict[str, int] = {}
    for finding in findings_payload.get("findings") or []:
        if isinstance(finding, dict):
            severity = str(finding.get("severity", "info"))
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

    module_durations: dict[str, int] = {}
    module_results_dir = run_dir / "module-results"
    if module_results_dir.is_dir():
        for path in module_results_dir.glob("*.json"):
            data = _load_json(path)
            module_result = data.get("module_result")
            if not isinstance(module_result, dict):
                continue
            module_name = str(module_result.get("name", ""))
            duration = module_result.get("duration_ms")
            if module_name and isinstance(duration, int | float):
                module_durations[module_name] = int(duration)

    target = run_payload.get("target") or {}
    quality = run_payload.get("quality_score")

    return RunMetrics(
        run_id=str(run_payload.get("run_id", run_dir.name)),
        status=str(run_payload.get("status", "")),
        quality_score=float(quality) if isinstance(quality, int | float) else None,
        target_host=str(target.get("host", "")),
        started_at=str(run_payload.get("started_at", "")),
        duration_ms=_parse_duration_ms(run_payload),
        findings_by_severity=severity_counts,
        module_durations_ms=module_durations,
    )


__all__ = ["RunMetrics", "extract_run_metrics"]
