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

from engine.reporter.dispatcher import (
    SUPPORTED_FORMATS,
    Reporter,
    ReporterPlugin,
    ReportFormat,
    ReportInputs,
    register_reporter_hook,
)
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
from engine.reporter.junit_writer import (
    FAILURE_SEVERITIES,
    render_junit_xml,
    write_junit,
)
from engine.reporter.markdown_writer import (
    RELEASE_DECISION_LABEL,
    SEVERITY_LABEL,
    SEVERITY_ORDER,
    md_escape,
    render_markdown,
    write_markdown,
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
from engine.reporter.sarif_rules import (
    SarifRule,
    SarifRuleRegistry,
    default_sarif_registry,
)
from engine.reporter.sarif_writer import (
    SARIF_SCHEMA_URI,
    SARIF_VERSION,
    SEVERITY_TO_LEVEL,
    build_sarif_document,
    write_sarif,
)
from engine.reporter.score_writer import (
    COMPONENT_AXES,
    DEFAULT_POLICY,
    SCORE_REPORT_SCHEMA_VERSION,
    SEVERITY_BUCKETS,
    write_score,
)

__all__ = [
    "ARTIFACT_SLOTS",
    "COMPONENT_AXES",
    "DEFAULT_POLICY",
    "FAILURE_SEVERITIES",
    "SUPPORTED_FORMATS",
    "Reporter",
    "ReporterPlugin",
    "ReportFormat",
    "ReportInputs",
    "register_reporter_hook",
    "FINDINGS_ENVELOPE_SCHEMA_VERSION",
    "FindingsLinterWarning",
    "RELEASE_DECISION_LABEL",
    "RUN_REPORT_SCHEMA_VERSION",
    "RunReport",
    "SARIF_SCHEMA_URI",
    "SARIF_VERSION",
    "SCORE_REPORT_SCHEMA_VERSION",
    "SEVERITY_BUCKETS",
    "SEVERITY_LABEL",
    "SEVERITY_ORDER",
    "SEVERITY_TO_LEVEL",
    "SarifRule",
    "SarifRuleRegistry",
    "build_run_report",
    "build_sarif_document",
    "canonical_config_digest",
    "collect_linter_warnings",
    "default_sarif_registry",
    "derive_release_decision",
    "first_blocking_warning",
    "lint_finding",
    "lint_findings",
    "md_escape",
    "render_junit_xml",
    "render_markdown",
    "summarize_modules_and_findings",
    "write_findings",
    "write_junit",
    "write_markdown",
    "write_run",
    "write_sarif",
    "write_score",
]
