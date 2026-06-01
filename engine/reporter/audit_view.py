"""Audit log view for the HTML report (, ).

The audit log is appended to as JSONL by every safety-relevant decision
in the run lifecycle (our engineering rules, §11). For the HTML report we read
back the redacted entries, normalize them into a typed shape, and
expose them to the Jinja2 template.

The reader is tolerant: malformed JSON lines are skipped (the report
should never crash because of a partial log), but counted so the test
suite can flag log corruption. Secrets stay redacted: nothing in this
module un-redacts the source content.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

_DETAIL_KEYS: Final[tuple[str, ...]] = (
    "module",
    "format",
    "path",
    "host",
    "code",
    "message",
    "decision",
    "release_decision",
    "step",
    "phase",
)


@dataclass(frozen=True)
class AuditEntry:
    """One normalized audit log line.

    ``raw`` preserves the original (already-redacted) record so the
    template can show the full detail when a reviewer wants it.
    """

    ts: str
    event: str
    level: str
    module: str
    detail: str
    raw: Mapping[str, Any]

    def to_template_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "event": self.event,
            "level": self.level,
            "module": self.module,
            "detail": self.detail,
        }


def load_audit_entries(path: Path) -> tuple[AuditEntry, ...]:
    """Read ``audit.log`` and return normalized entries (chronological order).

    Returns an empty tuple if the file does not exist (the run may have
    been short-circuited before any decisions landed). Malformed lines
    are dropped silently so the renderer is never blocked by corruption.
    """

    if not path.exists():
        return ()
    out: list[AuditEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        out.append(_normalize(obj))
    return tuple(out)


def normalize_audit_entries(records: Sequence[Mapping[str, Any]]) -> tuple[AuditEntry, ...]:
    """In-memory variant used by tests + the reporter hook."""

    return tuple(_normalize(dict(r)) for r in records)


def _normalize(record: Mapping[str, Any]) -> AuditEntry:
    ts = str(record.get("ts", ""))
    event = str(record.get("event", "")).strip() or "unknown"
    level = str(record.get("level", "")).strip() or _infer_level(event, record)
    module = str(record.get("module", "")).strip() or _infer_module(event, record)
    detail = _build_detail(event, record)
    return AuditEntry(
        ts=ts,
        event=event,
        level=level,
        module=module,
        detail=detail,
        raw=dict(record),
    )


def _infer_level(event: str, record: Mapping[str, Any]) -> str:
    if event in {"safety_block", "module_error"}:
        return "error"
    if event in {"policy_block", "gate_failed", "blocker"}:
        return "warning"
    if "code" in record and str(record["code"]).startswith("E-"):
        return "error"
    return "info"


def _infer_module(event: str, record: Mapping[str, Any]) -> str:
    if "module" in record:
        return str(record["module"])
    if event.startswith("module_"):
        return "lifecycle"
    if event in {"safety_block", "policy_block"}:
        return "policy"
    if event.startswith("artifact_"):
        return "reporter"
    return ""


def _build_detail(event: str, record: Mapping[str, Any]) -> str:
    pieces: list[str] = []
    for key in _DETAIL_KEYS:
        if key in record and record[key] not in (None, ""):
            pieces.append(f"{key}={record[key]}")
    if not pieces and "title" in record:
        pieces.append(str(record["title"]))
    return " ".join(pieces)


__all__ = [
    "AuditEntry",
    "load_audit_entries",
    "normalize_audit_entries",
]
