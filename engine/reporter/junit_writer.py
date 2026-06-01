"""JUnit XML emitter.

Emits a JUnit/Surefire-compatible XML report so any CI provider can
ingest SentinelQA results out of the box. The XSD lives at
``packages/shared-schema/external/junit.xsd``; the writer is validated
against that XSD in :mod:`tests.golden.reports.test_junit_xml`.

Mapping (our engineering rules — every report must answer "what / where / how
severe / why / how to fix"):

- One ``<testsuite>`` per module.
- Modules with no findings emit a single synthetic ``<testcase>`` for
 the module itself, so CI dashboards always show *something* for the
 module.
- Each finding becomes one ``<testcase>``. Severity ``critical`` /
 ``high`` produces a ``<failure>`` child; other severities pass.
- A module with ``status="errored"`` emits an ``<error>`` testcase
 carrying the captured error messages.
- A module with ``status="skipped"`` emits a ``<skipped>`` testcase.
- Redacted log excerpts ride along in ``<system-out>`` per our engineering rules
 §33 — every payload still passes through the existing redaction
 layer because :meth:`ArtifactDirectory.write_text` is the only sink.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final
from xml.etree import ElementTree as ET

from engine.domain.finding import Finding, Severity
from engine.domain.module_result import ModuleResult
from engine.domain.test_run import TestRun
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.redaction import redact

# Severities that promote a finding into a `<failure>` element. Other
# severities still get a testcase entry so they appear in dashboards.
FAILURE_SEVERITIES: Final[frozenset[Severity]] = frozenset({"critical", "high"})


def write_junit(
    artifact_dir: ArtifactDirectory,
    run: TestRun,
    *,
    module_results: Sequence[ModuleResult] = (),
    findings: Sequence[Finding] = (),
    system_out: str | None = None,
    filename: str = "junit.xml",
) -> Path:
    """Render and persist a JUnit XML report. Returns the written path."""

    root = _build_xml(
        run=run,
        module_results=module_results,
        findings=findings,
        system_out=system_out,
    )
    # Apply redaction at the string boundary so any leaked literal in
    # message attributes / cdata bodies gets masked even though the
    # writer already redacts ModuleResult.errors etc. upstream.
    serialized = ET.tostring(root, encoding="unicode")
    redacted_xml = _redact_xml(serialized)
    document = '<?xml version="1.0" encoding="UTF-8"?>\n' + redacted_xml + "\n"
    return artifact_dir.write_text(filename, document)


def render_junit_xml(
    run: TestRun,
    *,
    module_results: Sequence[ModuleResult] = (),
    findings: Sequence[Finding] = (),
    system_out: str | None = None,
) -> str:
    """Render to a string (no I/O). Useful for tests + previews."""

    root = _build_xml(
        run=run,
        module_results=module_results,
        findings=findings,
        system_out=system_out,
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + _redact_xml(ET.tostring(root, encoding="unicode"))
        + "\n"
    )


def _build_xml(
    *,
    run: TestRun,
    module_results: Sequence[ModuleResult],
    findings: Sequence[Finding],
    system_out: str | None,
) -> ET.Element:
    """Assemble the ``<testsuites>`` element."""

    findings_by_module: dict[str, list[Finding]] = {}
    for f in findings:
        findings_by_module.setdefault(f.module, []).append(f)

    suites: list[ET.Element] = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time_s": 0.0}

    # Modules listed in module_results take priority. Findings whose
    # module isn't represented still get a stand-in suite at the end so
    # nothing is silently dropped.
    seen_modules: set[str] = set()
    for module in module_results:
        suite = _build_suite(
            name=module.name,
            duration_ms=module.duration_ms,
            status=module.status,
            errors=tuple(module.errors),
            findings=tuple(findings_by_module.get(module.name, ())),
        )
        suites.append(suite)
        seen_modules.add(module.name)
        _accumulate(totals, suite)

    for mod_name, mod_findings in findings_by_module.items():
        if mod_name in seen_modules:
            continue
        suite = _build_suite(
            name=mod_name,
            duration_ms=0,
            status="passed",
            errors=(),
            findings=tuple(mod_findings),
        )
        suites.append(suite)
        _accumulate(totals, suite)

    root = ET.Element(
        "testsuites",
        attrib={
            "name": f"sentinelqa-{run.id}",
            "tests": str(totals["tests"]),
            "failures": str(totals["failures"]),
            "errors": str(totals["errors"]),
            "skipped": str(totals["skipped"]),
            "time": _format_seconds(totals["time_s"]),
        },
    )
    for suite in suites:
        root.append(suite)
    if system_out:
        root_sout = ET.SubElement(root, "system-out")
        root_sout.text = system_out
    return root


def _build_suite(
    *,
    name: str,
    duration_ms: int,
    status: str,
    errors: tuple[str, ...],
    findings: tuple[Finding, ...],
) -> ET.Element:
    """Build one ``<testsuite>`` element."""

    seconds = duration_ms / 1000.0
    suite = ET.Element(
        "testsuite",
        attrib={
            "name": name,
            "classname": f"sentinelqa.{name}",
            "tests": "0",  # patched below
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "time": _format_seconds(seconds),
        },
    )

    tests = failures = errors_count = skipped_count = 0

    if status == "errored":
        case = ET.SubElement(
            suite,
            "testcase",
            attrib={
                "name": name,
                "classname": f"sentinelqa.{name}",
                "time": _format_seconds(seconds),
            },
        )
        err = ET.SubElement(
            case,
            "error",
            attrib={
                "message": (errors[0] if errors else "module errored").strip()[:300],
                "type": "ModuleError",
            },
        )
        err.text = "\n".join(errors) if errors else "module errored"
        tests += 1
        errors_count += 1
    elif status == "skipped":
        case = ET.SubElement(
            suite,
            "testcase",
            attrib={"name": name, "classname": f"sentinelqa.{name}", "time": "0.000"},
        )
        ET.SubElement(case, "skipped", attrib={"message": "module skipped"})
        tests += 1
        skipped_count += 1
    elif not findings:
        # A passing module with no findings still emits one synthetic
        # testcase so CI sees the module ran.
        ET.SubElement(
            suite,
            "testcase",
            attrib={
                "name": name,
                "classname": f"sentinelqa.{name}",
                "time": _format_seconds(seconds),
            },
        )
        tests += 1

    for f in findings:
        case = ET.SubElement(
            suite,
            "testcase",
            attrib={
                "name": f.id,
                "classname": f"sentinelqa.{f.module}.{_safe_classname(f.category)}",
                "time": _format_seconds(seconds / max(len(findings), 1)),
            },
        )
        tests += 1
        if f.severity in FAILURE_SEVERITIES:
            failure = ET.SubElement(
                case,
                "failure",
                attrib={"message": f.title[:300], "type": f.severity},
            )
            failure.text = _failure_body(f)
            failures += 1

    suite.set("tests", str(tests))
    suite.set("failures", str(failures))
    suite.set("errors", str(errors_count))
    suite.set("skipped", str(skipped_count))
    return suite


def _failure_body(f: Finding) -> str:
    lines = [
        f"Severity: {f.severity}",
        f"Confidence: {f.confidence:.2f}",
        f"Description: {f.description}",
    ]
    if f.recommendation:
        lines.append(f"Recommendation: {f.recommendation}")
    if f.location.route:
        lines.append(f"Route: {f.location.route}")
    if f.location.file:
        lines.append(f"File: {f.location.file}")
    if f.evidence:
        lines.append("Evidence:")
        for ev in f.evidence:
            lines.append(f"  - {ev.type}: {ev.path}")
    return "\n".join(lines)


def _accumulate(totals: dict[str, int | float], suite: ET.Element) -> None:
    totals["tests"] = int(totals["tests"]) + int(suite.get("tests", "0"))
    totals["failures"] = int(totals["failures"]) + int(suite.get("failures", "0"))
    totals["errors"] = int(totals["errors"]) + int(suite.get("errors", "0"))
    totals["skipped"] = int(totals["skipped"]) + int(suite.get("skipped", "0"))
    totals["time_s"] = float(totals["time_s"]) + float(suite.get("time", "0"))


def _format_seconds(value: float) -> str:
    # Three-decimal seconds is the surefire-default and reads naturally.
    return f"{float(value):.3f}"


def _safe_classname(category: str) -> str:
    """Make a category safe to interpolate into a Java-ish classname."""

    return "".join(ch if ch.isalnum() else "_" for ch in category) or "unknown"


def _redact_xml(serialized: str) -> str:
    """Apply :func:`engine.policy.redaction.redact` to the XML string.

    We model the document as a single ``str`` so the redaction layer can
    walk it. Walking the ElementTree directly would skip attribute
    values, so the simpler approach is to redact the rendered string.
    """

    return _coerce_redacted_str(redact(serialized))


def _coerce_redacted_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise AssertionError(f"redact returned non-string for XML body: {type(value)!r}")


def known_failure_severities() -> Iterable[str]:
    """Return severities that produce `<failure>` (test helper)."""

    return tuple(FAILURE_SEVERITIES)


__all__ = [
    "FAILURE_SEVERITIES",
    "known_failure_severities",
    "render_junit_xml",
    "write_junit",
]
