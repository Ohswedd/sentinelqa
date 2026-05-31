"""``findings.json`` writer (task 03.02).

Serializes the findings envelope from a sequence of :class:`Finding`
instances. Schema lives at ``packages/shared-schema/findings.schema.json``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.domain.finding import Finding
from engine.errors.base import ConfigError
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.findings_linter import (
    FindingsLinterWarning,
    first_blocking_warning,
    lint_findings,
)

FINDINGS_ENVELOPE_SCHEMA_VERSION: str = "2"
"""Envelope wire version. Tracks ``FINDINGS_SCHEMA_VERSION`` 1:1; bumped
to ``"2"`` in Phase 32 / ADR-0044 to match the per-finding schema bump."""


def write_findings(
    artifact_dir: ArtifactDirectory,
    findings: Sequence[Finding],
    *,
    run_id: str,
    generated_at: datetime | None = None,
    enforce_evidence: bool = True,
    filename: str = "findings.json",
) -> Path:
    """Write a findings envelope to ``filename`` and return its path.

    ``enforce_evidence`` (default True) raises :class:`ConfigError` if any
    finding with ``severity >= medium`` lacks evidence. The vague-finding
    linter runs unconditionally and its warnings are returned via
    :func:`collect_linter_warnings`; the writer does not fail on them.

    Redaction is applied by :meth:`ArtifactDirectory.write_json` (already
    runs every payload through :func:`engine.policy.redaction.redact`).
    """

    if enforce_evidence:
        blocker = first_blocking_warning(findings)
        if blocker is not None:
            raise ConfigError(
                detail=(f"Finding {blocker.finding_id} blocked the writer: {blocker.message}"),
            )

    when = generated_at or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    envelope: dict[str, Any] = {
        "schema_version": FINDINGS_ENVELOPE_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": when.astimezone(UTC).isoformat(),
        "count": len(findings),
        "findings": [_finding_payload(f) for f in findings],
    }
    return artifact_dir.write_json(filename, envelope)


def collect_linter_warnings(
    findings: Sequence[Finding],
) -> list[FindingsLinterWarning]:
    """Helper exposed so the orchestrator can record warnings on the run."""

    return lint_findings(findings)


def _finding_payload(finding: Finding) -> dict[str, Any]:
    """Coerce a :class:`Finding` to the wire shape (sorts evidence by id)."""

    payload = finding.to_dict()
    # Stable ordering for nested arrays so byte comparisons in goldens hold.
    if isinstance(payload.get("evidence"), list):
        payload["evidence"] = sorted(payload["evidence"], key=lambda e: e["id"])
    if isinstance(payload.get("reproduction_steps"), list):
        # Reproduction step ordering is meaningful — preserve as-is.
        pass
    return payload


__all__ = [
    "FINDINGS_ENVELOPE_SCHEMA_VERSION",
    "collect_linter_warnings",
    "write_findings",
]
