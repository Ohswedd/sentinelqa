"""Shared helpers for the ``*_audit`` tools (audit / security / perf / a11y).

Every audit-shaped tool:

1. Enforces safety on the URL.
2. Calls :meth:`Sentinel.async_audit` with the appropriate module
   subset.
3. Translates the :class:`AuditResult` into the on-wire result payload.
4. Collects evidence refs from the run dir.

This module is the single source of truth for that translation.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sentinelqa import AuditResult


def audit_result_to_payload(result: AuditResult) -> dict[str, Any]:
    """Render an :class:`AuditResult` as the canonical tool result payload."""

    return {
        "schema_version": result.SCHEMA_VERSION,
        "run_id": result.run_id,
        "status": result.status,
        "release_decision": result.release_decision,
        "quality_score": result.quality_score,
        "target_url": result.target_url,
        "modules_run": list(result.modules_run),
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "config_digest": result.config_digest,
        "passed": result.passed,
        "run_dir": str(result.run_dir),
        "findings": [f.to_agent_message() for f in result.findings],
        "agent_messages": [dict(m) for m in result.to_agent_messages()],
    }


def collect_evidence_refs(result: AuditResult) -> tuple[str, ...]:
    """Return the canonical evidence file list under ``result.run_dir``.

    We surface only the files the agent can fetch via
    ``sentinel.read_report`` — the per-run report directory contents.
    Directories and traces are omitted; the agent can probe with
    ``read_report --path`` if it needs deeper artifacts.
    """

    if not result.run_dir.exists():
        return ()
    refs: list[str] = []
    for entry in sorted(result.run_dir.iterdir()):
        if entry.is_file():
            refs.append(entry.name)
    return tuple(refs)


def parse_optional_modules(args: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Pluck a ``modules`` arg as a tuple of names (or ``None``)."""

    raw = args.get("modules")
    if raw is None:
        return None
    if isinstance(raw, str):
        return (raw,) if raw else None
    if isinstance(raw, list):
        return tuple(str(m).strip() for m in raw if str(m).strip())
    return None


def safe_relative(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` as a forward-slash string.

    Falls back to the absolute path when the file lives outside ``root``.
    """

    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path.resolve())
    return rel.as_posix()


__all__ = [
    "audit_result_to_payload",
    "collect_evidence_refs",
    "parse_optional_modules",
    "safe_relative",
]
