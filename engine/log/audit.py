"""Audit log facade (our engineering rules, §26).

Operational logs (info/warn/error) and audit logs (safety decisions, policy
gate outcomes) are kept on distinct streams. Audit entries always land at
``.sentinel/runs/<run-id>/audit.log`` and ALSO get logged at INFO level on
the ``sentinelqa.audit`` logger so verbose mode surfaces them on stderr.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.log import get_logger
from engine.policy.audit_log import write_audit_entry

_logger = get_logger("audit")


def log_audit(path: Path | None, entry: dict[str, Any]) -> None:
    """Persist ``entry`` to the run audit log AND emit it on the audit logger."""

    if path is not None:
        write_audit_entry(path, entry)
    _logger.info("audit", extra={"audit_entry": entry})


__all__ = ["log_audit"]
