"""SentinelQA report writers.

The reporter is the single place that turns in-memory domain objects
(:class:`engine.domain.test_run.TestRun`, :class:`engine.domain.finding.Finding`,
:class:`engine.domain.quality_score.QualityScore`,
:class:`engine.domain.policy_decision.PolicyDecision`) into the wire formats
SentinelQA writes to ``.sentinel/runs/<run-id>/``.

Real, content-rich HTML / PR-comment / trend reports land in. Phase
03 only ships the **machine-readable** envelopes and their schemas so the
wire formats are stable and versioned (our engineering rules, §38). Re-exports grow
task by task as each writer is added.
"""

from __future__ import annotations

from engine.reporter.audit_view import (
    AuditEntry,
    load_audit_entries,
    normalize_audit_entries,
)
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
from engine.reporter.html_writer import (
    HTML_REPORT_SCHEMA_VERSION,
    HtmlReportInputs,
    build_template_context,
    collect_artifact_links,
    render_html_report,
    write_html,
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
from engine.reporter.pr_comment import (
    PR_COMMENT_ANCHOR,
    PR_COMMENT_MAX_CHARS,
    render_pr_comment,
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
from engine.reporter.slack import (
    SLACK_PAYLOAD_SCHEMA_PATH,
    load_block_kit_schema,
    render_slack_payload,
    write_slack_payload,
)
from engine.reporter.trends import (
    ModulePassRateSeries,
    TopRecurring,
    TrendData,
    TrendPoint,
    compute_trends,
)

__all__ = [
    "ARTIFACT_SLOTS",
    "AuditEntry",
    "COMPONENT_AXES",
    "DEFAULT_POLICY",
    "FAILURE_SEVERITIES",
    "HTML_REPORT_SCHEMA_VERSION",
    "HtmlReportInputs",
    "ModulePassRateSeries",
    "PR_COMMENT_ANCHOR",
    "PR_COMMENT_MAX_CHARS",
    "SLACK_PAYLOAD_SCHEMA_PATH",
    "SUPPORTED_FORMATS",
    "Reporter",
    "ReporterPlugin",
    "ReportFormat",
    "ReportInputs",
    "TopRecurring",
    "TrendData",
    "TrendPoint",
    "build_template_context",
    "collect_artifact_links",
    "compute_trends",
    "load_audit_entries",
    "load_block_kit_schema",
    "normalize_audit_entries",
    "register_reporter_hook",
    "render_html_report",
    "render_pr_comment",
    "render_slack_payload",
    "write_html",
    "write_slack_payload",
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
