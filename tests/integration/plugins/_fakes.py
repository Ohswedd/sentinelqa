"""Concrete plugin classes used across the integration tests.

Kept out of conftest so we can also import them directly from tests
without worrying about pytest fixture state.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult


def _empty_module_result(name: str) -> ModuleResult:
    ids = IdGenerator()
    return ModuleResult(
        id=ids.new("MOD"),
        name=name,
        status="passed",
        findings=(),
        metrics={},
        duration_ms=0,
        errors=(),
    )


class TinyScanner:
    """A minimal valid scanner."""

    kind = "scanner"
    name = "tiny-scanner"
    version = "0.1.0"
    capabilities = frozenset({"audit"})
    permissions = frozenset({"fs.read"})
    requires_protocol = ">=1.0,<2.0"
    description = "Reference scanner for tests."

    def run(self, context: Any) -> ModuleResult:
        return _empty_module_result(self.name)


class ScannerNeedingArtifact:
    """Scanner that exercises ``PluginContext.artifact_path``."""

    kind = "scanner"
    name = "artifact-scanner"
    version = "0.1.0"
    capabilities = frozenset({"audit"})
    permissions = frozenset({"fs.write:.sentinel/runs"})
    requires_protocol = ">=1.0,<2.0"
    description = "Writes an artifact under the run dir."

    def run(self, context: Any) -> ModuleResult:
        out = context.artifact_path("scanner.json")
        out.write_text("{}", encoding="utf-8")
        return _empty_module_result(self.name)


class ForbiddenScanner:
    """Scanner that declares a forbidden capability (CLAUDE §6)."""

    kind = "scanner"
    name = "bad-scanner"
    version = "0.1.0"
    capabilities = frozenset({"audit", "stealth_automation"})
    permissions = frozenset({"fs.read"})
    requires_protocol = ">=1.0,<2.0"

    def run(self, context: Any) -> ModuleResult:
        return _empty_module_result(self.name)


class IncompatibleScanner:
    """Scanner requiring a future protocol version."""

    kind = "scanner"
    name = "future-scanner"
    version = "0.1.0"
    capabilities: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    requires_protocol = ">=2.0,<3.0"

    def run(self, context: Any) -> ModuleResult:
        return _empty_module_result(self.name)


class BadShapeScanner:
    """Scanner missing the run() method — must fail the Protocol check."""

    kind = "scanner"
    name = "broken-scanner"
    version = "0.1.0"
    capabilities: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    requires_protocol = ">=1.0,<2.0"

    # No run() method — isinstance(..., ScannerPlugin) must fail.


class TinyReporter:
    """A minimal valid reporter."""

    kind = "reporter"
    name = "csv-reporter"
    version = "0.1.0"
    capabilities = frozenset({"report"})
    permissions = frozenset({"fs.write:.sentinel/runs"})
    requires_protocol = ">=1.0,<2.0"
    description = "Emits a CSV summary."
    formats: tuple[str, ...] = ("csv",)

    def emit(self, result: Any, context: Any) -> Mapping[str, Path]:
        out = context.artifact_path("report.csv")
        out.write_text("module,findings\n", encoding="utf-8")
        return {"csv": out}
