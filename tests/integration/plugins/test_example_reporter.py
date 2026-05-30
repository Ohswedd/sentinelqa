"""Phase 24 task 24.06 — reference reporter example test."""

from __future__ import annotations

import csv

# Add the example to sys.path.
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.plugins import build_plugin_context, load_from_entry_point

from sentinelqa import AuditResult, Finding

EXAMPLE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "examples"
    / "plugins"
    / "sentinelqa-reporter-example"
    / "src"
)
sys.path.insert(0, str(EXAMPLE_ROOT))

from sentinelqa_reporter_example.plugin import CsvReporter  # type: ignore[import-not-found]  # noqa: E402, I001


def _audit_result(findings: tuple[Finding, ...] = ()) -> AuditResult:
    return AuditResult(
        run_id="RUN-BBBBBBBBBBBB",
        status="passed" if not findings else "failed",
        release_decision="pass",
        quality_score=99.5,
        findings=findings,
        module_results=(),
        run_dir=Path("/tmp/run"),
        started_at=datetime(2026, 5, 30, tzinfo=UTC),
        finished_at=datetime(2026, 5, 30, tzinfo=UTC),
        config_digest="abc",
        target_url="http://localhost",
        modules_run=("header-checker",),
    )


def _ctx(tmp_path: Path) -> object:
    return build_plugin_context(
        plugin_name="csv-reporter",
        run_id="RUN-BBBBBBBBBBBB",
        target_url="http://localhost",
        run_dir=tmp_path,
        config_snapshot={},
        granted_permissions=frozenset({"fs.write:.sentinel/runs"}),
    )


def test_csv_reporter_writes_header_only_on_empty_findings(tmp_path: Path) -> None:
    plugin = CsvReporter()
    out = plugin.emit(_audit_result(), _ctx(tmp_path))
    csv_path = out["csv"]
    content = csv_path.read_text(encoding="utf-8")
    assert content.splitlines() == ["finding_id,severity,module,title"]


def test_csv_reporter_writes_findings(tmp_path: Path) -> None:
    findings = (
        Finding(
            id="FND-CCCCCCCCCCCC",
            run_id="RUN-BBBBBBBBBBBB",
            module="header-checker",
            category="header-misconfig",
            severity="low",
            confidence=0.9,
            title="X-Frame-Options missing",
            description="missing",
            created_at=datetime(2026, 5, 30, tzinfo=UTC),
        ),
    )
    plugin = CsvReporter()
    out = plugin.emit(_audit_result(findings), _ctx(tmp_path))

    rows = list(csv.reader(out["csv"].open(encoding="utf-8")))
    assert rows[0] == ["finding_id", "severity", "module", "title"]
    assert rows[1] == [
        "FND-CCCCCCCCCCCC",
        "low",
        "header-checker",
        "X-Frame-Options missing",
    ]


def test_csv_reporter_isinstance_reporter_protocol() -> None:
    from sentinelqa.plugins import ReporterPlugin

    assert isinstance(CsvReporter(), ReporterPlugin)


def test_csv_reporter_loads_from_synthetic_entry_point(make_entry_point) -> None:
    ep = make_entry_point(
        "csv-reporter",
        "tests.fakes.csv_entry:CsvReporter",
        CsvReporter,
    )
    loaded = load_from_entry_point(ep)
    assert loaded.manifest.name == "csv-reporter"
    assert loaded.manifest.kind == "reporter"


def test_csv_reporter_refuses_without_write_permission(tmp_path: Path) -> None:
    from engine.plugins.errors import PluginPermissionError

    ctx = build_plugin_context(
        plugin_name="csv-reporter",
        run_id="RUN-BBBBBBBBBBBB",
        target_url="http://localhost",
        run_dir=tmp_path,
        config_snapshot={},
        granted_permissions=frozenset(),
    )
    with pytest.raises(PluginPermissionError):
        CsvReporter().emit(_audit_result(), ctx)
