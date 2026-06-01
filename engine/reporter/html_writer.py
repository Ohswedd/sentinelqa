"""HTML report writer (, ).

Produces the final `report.html` for a run by rendering the Jinja2
template at :data:`HTML_TEMPLATE_PATH` against the typed inputs.

The bundled CSS + JS live next to the template; both are inlined into
the rendered HTML so the file is self-contained: it opens correctly
from ``file://`` and never hits the network.

Determinism contract:

- Sort order for findings + modules + audit entries is locked.
- The rendered HTML is byte-stable across runs given identical inputs.
- All user-controlled strings flow through Jinja2's autoescape so a
 malicious finding title cannot inject markup.

The writer integrates with the Phase-03 :class:`Reporter` dispatcher
via :func:`render_html_report` (called from
``engine.reporter.dispatcher.Reporter.emit`` when ``html`` is in the
configured formats).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from engine.domain.finding import Finding, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision, ReleaseDecision
from engine.domain.quality_score import QualityScore
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.reporter.audit_view import AuditEntry
from engine.reporter.markdown_writer import (
    RELEASE_DECISION_LABEL,
    SEVERITY_LABEL,
    SEVERITY_ORDER,
)
from engine.reporter.trends import TrendData

HTML_REPORT_SCHEMA_VERSION: Final[str] = "1"
"""Locked HTML envelope version. Bump on breaking template changes."""

HTML_ASSETS_DIR: Final[Path] = Path(__file__).parent / "html"
HTML_TEMPLATE_PATH: Final[Path] = HTML_ASSETS_DIR / "template.html.j2"
HTML_STYLES_PATH: Final[Path] = HTML_ASSETS_DIR / "styles.css"
HTML_APP_JS_PATH: Final[Path] = HTML_ASSETS_DIR / "app.js"

_IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
)

_SEVERITY_RANK: Final[dict[Severity, int]] = {s: i for i, s in enumerate(SEVERITY_ORDER)}


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(HTML_ASSETS_DIR)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html", "htm", "xml", "j2"]),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


@dataclass(frozen=True)
class HtmlReportInputs:
    """Bundle of typed inputs the HTML writer needs.

    Trends + audit log are optional — the renderer drops the trends
    section when there is no history and the audit section when the
    audit log is empty (our product spec — answers the question; no fake data).
    """

    run: TestRun
    findings: tuple[Finding, ...] = ()
    module_results: tuple[ModuleResult, ...] = ()
    score: QualityScore | None = None
    policy: PolicyDecision | None = None
    config_digest: str = ""
    audit_entries: tuple[AuditEntry, ...] = ()
    trends: TrendData | None = None
    artifact_links: tuple[Mapping[str, str], ...] = ()


def write_html(
    artifact_dir: ArtifactDirectory,
    inputs: HtmlReportInputs,
    *,
    filename: str = "report.html",
) -> Path:
    """Render and persist ``report.html``. Returns the written path."""

    html = render_html_report(inputs)
    target = artifact_dir.path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def render_html_report(inputs: HtmlReportInputs) -> str:
    """Render the HTML document as a string (no I/O)."""

    env = _make_env()
    template = env.get_template(HTML_TEMPLATE_PATH.name)
    context = build_template_context(inputs)
    return template.render(**context)


def build_template_context(inputs: HtmlReportInputs) -> dict[str, Any]:
    """Turn the typed inputs into the Jinja2 context dict.

    Pure function — tests construct it directly to assert on the shape
    instead of parsing rendered HTML.
    """

    run = inputs.run
    findings = sorted(
        inputs.findings,
        key=lambda f: (_SEVERITY_RANK.get(f.severity, len(SEVERITY_ORDER)), f.id),
    )
    blockers = [f for f in findings if f.severity in {"critical", "high"}]

    release_decision: ReleaseDecision
    if inputs.policy is not None:
        release_decision = inputs.policy.release_decision
    elif run.status == "unsafe_blocked":
        release_decision = "unsafe_target_rejected"
    elif run.status == "dry_run":
        release_decision = "inconclusive"
    elif run.status == "passed":
        release_decision = "pass"
    elif run.status == "failed":
        release_decision = "blocked"
    else:
        release_decision = "inconclusive"

    score_value: float | None
    if run.status in {"unsafe_blocked", "dry_run"} or inputs.score is None:
        score_value = None
    else:
        score_value = round(float(inputs.score.total), 2)

    counts: dict[Severity, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    counts_summary = (
        ", ".join(
            f"{counts[s]} {SEVERITY_LABEL[s].lower()}"
            for s in SEVERITY_ORDER
            if counts.get(s, 0) > 0
        )
        or "0 findings"
    )

    modules_sorted = sorted(inputs.module_results, key=lambda m: m.name)
    finding_counts_by_module: dict[str, int] = {}
    for f in findings:
        finding_counts_by_module[f.module] = finding_counts_by_module.get(f.module, 0) + 1

    module_rows = []
    for m in modules_sorted:
        flake_rate = None
        for key in ("flake_rate", "flake.rate"):
            if key in m.metrics:
                flake_rate = m.metrics[key]
                break
        module_rows.append(
            {
                "name": m.name,
                "status": m.status,
                "status_label": m.status,
                "duration_display": _duration_display_ms(m.duration_ms),
                "finding_count": finding_counts_by_module.get(m.name, 0),
                "flake_rate": _format_flake_rate(flake_rate),
            }
        )

    duration_display = "n/a"
    if run.finished_at is not None:
        delta = (run.finished_at - run.started_at).total_seconds()
        duration_display = f"{delta:.1f}s"

    parsed = urlparse(str(run.target.base_url))
    target_display = parsed.geturl()

    artifact_links: list[Mapping[str, str]] = list(inputs.artifact_links) or [
        {"href": "run.json", "label": "run.json"},
        {"href": "findings.json", "label": "findings.json"},
        {"href": "score.json", "label": "score.json"},
        {"href": "sarif.json", "label": "sarif.json"},
        {"href": "junit.xml", "label": "junit.xml"},
        {"href": "report.md", "label": "report.md"},
        {"href": "audit.log", "label": "audit.log"},
    ]

    findings_view = [_finding_view(f) for f in findings]
    blocker_view = [_finding_view(f) for f in blockers]
    module_options = sorted({f.module for f in findings})
    severity_options = [
        {"value": s, "label": SEVERITY_LABEL[s]} for s in SEVERITY_ORDER if counts.get(s, 0) > 0
    ]

    audit_entries = list(inputs.audit_entries)
    audit_levels = sorted({e.level for e in audit_entries if e.level})
    audit_modules = sorted({e.module for e in audit_entries if e.module})

    trends_ctx: Mapping[str, Any] | None = None
    if inputs.trends is not None:
        trends_ctx = inputs.trends.to_template_context()

    llm_audit_view = _build_llm_audit_view(findings, modules_sorted)

    return {
        "run": {
            "id": run.id,
            "status": run.status,
        },
        "target_display": target_display,
        "target_mode": run.target.mode,
        "duration_display": duration_display,
        "score_display": "n/a" if score_value is None else f"{score_value} / 100",
        "decision_label": RELEASE_DECISION_LABEL[release_decision],
        "decision_class": release_decision,
        "counts_summary": counts_summary,
        "module_summary": ", ".join(sorted({m.name for m in modules_sorted})) or "none",
        "blockers": blocker_view,
        "findings": findings_view,
        "severity_options": severity_options,
        "module_options": module_options,
        "module_results": module_rows,
        "audit_entries": [e.to_template_dict() for e in audit_entries],
        "audit_levels": audit_levels,
        "audit_modules": audit_modules,
        "trends": trends_ctx,
        "llm_audit": llm_audit_view,
        "schema_versions": {
            "run": "1",
            "findings": "1",
            "score": "1",
            "sarif": "2.1.0",
            "html": HTML_REPORT_SCHEMA_VERSION,
        },
        "config_digest": inputs.config_digest or "unavailable",
        "artifact_links": artifact_links,
        "inline_css": _read_asset(HTML_STYLES_PATH),
        "inline_js": _read_asset(HTML_APP_JS_PATH),
    }


def _finding_view(f: Finding) -> dict[str, Any]:
    """Project a :class:`Finding` into the template-facing shape."""

    location_parts: list[str] = []
    loc = f.location
    if loc is not None:
        if loc.route:
            location_parts.append(f"route={loc.route}")
        if loc.selector:
            location_parts.append(f"selector={loc.selector}")
        if loc.file:
            location_parts.append(f"file={loc.file}")
        if loc.line is not None:
            location_parts.append(f"line={loc.line}")
    if f.affected_target:
        location_parts.append(f"target={f.affected_target}")
    location_display = "; ".join(location_parts) or "—"

    evidence_view = []
    for ev in f.evidence:
        href = str(ev.path)
        suffix = Path(href).suffix.lower()
        evidence_view.append(
            {
                "href": href,
                "id": ev.id,
                "type": ev.type,
                "is_image": suffix in _IMAGE_SUFFIXES,
            }
        )

    search_text = " ".join(
        [
            f.id,
            f.title,
            f.module,
            f.category,
        ]
    )

    return {
        "id": f.id,
        "severity": f.severity,
        "severity_label": SEVERITY_LABEL[f.severity],
        "module": f.module,
        "category": f.category,
        "title": f.title,
        "description": f.description,
        "recommendation": f.recommendation or "",
        "confidence": round(float(f.confidence), 2),
        "evidence": evidence_view,
        "location_display": location_display,
        "search_text": search_text,
    }


def _read_asset(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _duration_display_ms(duration_ms: int) -> str:
    if duration_ms <= 0:
        return "0 ms"
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    return f"{duration_ms / 1000.0:.1f} s"


def _format_flake_rate(value: Any) -> str | None:
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    return f"{rate:.2%}"


def collect_artifact_links(produced: Mapping[str, Path]) -> tuple[dict[str, str], ...]:
    """Convert dispatcher output paths into the template's link rows."""

    label_overrides = {
        "run": "run.json",
        "findings": "findings.json",
        "score": "score.json",
        "junit": "junit.xml",
        "sarif": "sarif.json",
        "markdown": "report.md",
    }
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for fmt, path in sorted(produced.items()):
        href = path.name
        if href in seen:
            continue
        seen.add(href)
        rows.append({"href": href, "label": label_overrides.get(fmt, href)})
    rows.append({"href": "audit.log", "label": "audit.log"})
    return tuple(rows)


def iter_severity_buckets(findings: Iterable[Finding]) -> Sequence[Severity]:
    """Return the severities present in ``findings`` in display order."""

    present = {f.severity for f in findings}
    return tuple(s for s in SEVERITY_ORDER if s in present)


def _build_llm_audit_view(
    findings: Sequence[Finding],
    module_results: Sequence[ModuleResult],
) -> dict[str, Any] | None:
    """Build the LLM-audit section context (the documentation, §28 — differentiator).

    Returns ``None`` when the LLM-audit module did not run AND there are
    no LLM-audit findings, so the template hides the section silently.
    """

    llm_findings = [f for f in findings if f.module == "llm_audit"]
    has_module = any(m.name == "llm_audit" for m in module_results)
    if not llm_findings and not has_module:
        return None
    by_category: dict[str, list[Finding]] = {}
    for finding in llm_findings:
        by_category.setdefault(finding.category, []).append(finding)
    rule_rows: list[dict[str, Any]] = []
    for category in sorted(by_category):
        bucket = by_category[category]
        severities = {f.severity for f in bucket}
        highest = next(
            (s for s in SEVERITY_ORDER if s in severities),
            "info",
        )
        sample = bucket[0]
        rule_rows.append(
            {
                "category": category,
                "count": len(bucket),
                "highest_severity": highest,
                "sample_title": sample.title,
                "sample_route": (sample.location.route if sample.location else None) or "",
            }
        )
    return {
        "total_findings": len(llm_findings),
        "rules": rule_rows,
    }


__all__ = [
    "HTML_REPORT_SCHEMA_VERSION",
    "HtmlReportInputs",
    "build_template_context",
    "collect_artifact_links",
    "iter_severity_buckets",
    "render_html_report",
    "write_html",
]
