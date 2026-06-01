"""``CsvReporter`` — reference reporter that writes a CSV summary.

This plugin demonstrates the smallest possible SentinelQA reporter:

- Implements :class:`sentinelqa.plugins.ReporterPlugin`.
- Writes a single ``report.csv`` under the run's plugin artifact
  directory (sandboxed via :class:`PluginContext`).
- Returns ``{"csv": Path}`` so the dispatcher records the artifact.

Real reporters typically emit several files; this one stays minimal
to keep the contract visible.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from pathlib import Path

from sentinelqa import AuditResult
from sentinelqa.plugins import PluginContext


class CsvReporter:
    """Reference reporter plugin reference plugin."""

    kind = "reporter"
    name = "csv-reporter"
    version = "0.1.0"
    capabilities = frozenset({"report"})
    permissions = frozenset({"fs.write:.sentinel/runs"})
    requires_protocol = ">=1.0,<2.0"
    description = "Emits a CSV summary of the run's findings."
    formats: tuple[str, ...] = ("csv",)

    def emit(
        self,
        result: AuditResult,
        context: PluginContext,
    ) -> Mapping[str, Path]:
        path = context.artifact_path("report.csv")
        buf = StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["finding_id", "severity", "module", "title"])
        for finding in sorted(result.findings, key=lambda f: f.id):
            writer.writerow(
                [
                    finding.id,
                    finding.severity,
                    finding.module,
                    finding.title.replace("\n", " "),
                ]
            )
        path.write_text(buf.getvalue(), encoding="utf-8")
        return {"csv": path}
