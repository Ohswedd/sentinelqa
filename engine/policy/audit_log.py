"""Append-only audit log of safety decisions (CLAUDE.md §6, §26).

Each :class:`SafetyDecision` is serialized to one JSON line and appended to
the run's ``.sentinel/runs/<run-id>/audit.log`` file. The Phase 02 run
lifecycle owns directory creation; this module is fine with a path that
doesn't exist yet (the parent dir is created on first write).

Records are redacted via :func:`engine.policy.redaction.redact` before
they touch disk. There is no in-memory buffer — every decision is flushed
synchronously so a crash mid-run still leaves an investigable log.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.policy.redaction import redact


def write_audit_entry(path: Path, entry: dict[str, Any]) -> None:
    """Append a redacted, JSON-encoded ``entry`` line to ``path``."""

    redacted = redact(entry)
    assert isinstance(redacted, dict)
    redacted.setdefault("ts", datetime.now(UTC).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(redacted, separators=(",", ":"), sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_audit_log(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL audit log into a list of dicts (test helper)."""

    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        out.append(json.loads(stripped))
    return out


__all__ = ["write_audit_entry", "read_audit_log"]
