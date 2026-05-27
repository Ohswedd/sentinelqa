"""SentinelQA report writers (Phase 03).

The reporter is the single place that turns in-memory domain objects
(:class:`engine.domain.test_run.TestRun`, :class:`engine.domain.finding.Finding`,
:class:`engine.domain.quality_score.QualityScore`,
:class:`engine.domain.policy_decision.PolicyDecision`) into the wire formats
SentinelQA writes to ``.sentinel/runs/<run-id>/``.

Real, content-rich HTML / PR-comment / trend reports land in Phase 15. Phase
03 only ships the **machine-readable** envelopes and their schemas so the
wire formats are stable and versioned (CLAUDE.md §11, §38). Re-exports grow
task by task as each writer is added.
"""

from __future__ import annotations

from engine.reporter.findings_linter import (
    FindingsLinterWarning,
    first_blocking_warning,
    lint_finding,
    lint_findings,
)
from engine.reporter.findings_writer import (
    FINDINGS_ENVELOPE_SCHEMA_VERSION,
    collect_linter_warnings,
    write_findings,
)
from engine.reporter.run_writer import (
    ARTIFACT_SLOTS,
    RUN_REPORT_SCHEMA_VERSION,
    RunReport,
    build_run_report,
    canonical_config_digest,
    derive_release_decision,
    summarize_modules_and_findings,
    write_run,
)

__all__ = [
    "ARTIFACT_SLOTS",
    "FINDINGS_ENVELOPE_SCHEMA_VERSION",
    "FindingsLinterWarning",
    "RUN_REPORT_SCHEMA_VERSION",
    "RunReport",
    "build_run_report",
    "canonical_config_digest",
    "collect_linter_warnings",
    "derive_release_decision",
    "first_blocking_warning",
    "lint_finding",
    "lint_findings",
    "summarize_modules_and_findings",
    "write_findings",
    "write_run",
]
