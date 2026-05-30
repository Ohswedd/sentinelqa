"""``HeaderChecker`` — reference scanner that checks one HTTP header.

This plugin demonstrates the smallest possible SentinelQA scanner:

- Implements :class:`sentinelqa.plugins.ScannerPlugin`.
- Declares the minimal manifest (name / version / kind / capabilities
  / permissions / requires_protocol).
- Returns a typed :class:`ModuleResult` the orchestrator can score.

It looks for ``X-Frame-Options`` on the target URL and emits a single
``low``-severity finding when it's missing. Real plugins typically
emit many findings of varying severity; this one stays minimal so the
plugin lifecycle is the focus.
"""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator
from engine.domain.module_result import ModuleResult

from sentinelqa.plugins import PluginContext


class HeaderChecker:
    """Reference scanner plugin (PRD §22.2 example)."""

    kind = "scanner"
    name = "header-checker"
    version = "0.1.0"
    capabilities = frozenset({"http_check"})
    permissions = frozenset({"network.outbound", "fs.write:.sentinel/runs"})
    requires_protocol = ">=1.0,<2.0"
    description = "Reference scanner: checks for X-Frame-Options."

    def run(self, context: PluginContext) -> ModuleResult:
        ids = IdGenerator()
        headers = self._fetch(context.target_url, context=context)
        findings: tuple[Finding, ...] = ()
        if "x-frame-options" not in {k.lower() for k in headers}:
            finding = Finding(
                id=ids.new("FND"),
                run_id=context.run_id,
                module=self.name,
                category="header-misconfig",
                severity="low",
                confidence=0.9,
                title="X-Frame-Options missing",
                description=(
                    "The landing URL did not return X-Frame-Options; "
                    "browsers may allow framing the page."
                ),
                location=FindingLocation(route="/"),
                recommendation=(
                    "Set 'X-Frame-Options: DENY' (or a CSP frame-ancestors "
                    "directive) on the response."
                ),
                created_at=datetime.now(UTC),
            )
            findings = (finding,)

        status: str = "failed" if findings else "passed"
        return ModuleResult(
            id=ids.new("MOD"),
            name=self.name,
            status=status,
            findings=findings,
            metrics={"checked_headers": 1},
            duration_ms=0,
            errors=(),
        )

    # ------------------------------------------------------------------
    # Override hook (tests monkeypatch this).
    # ------------------------------------------------------------------
    def _fetch(
        self,
        url: str,
        *,
        context: PluginContext,
    ) -> dict[str, str]:
        # Real implementations would call httpx here. The example
        # avoids a runtime network dep so the test suite stays
        # hermetic — tests monkeypatch ``_fetch`` directly.
        return {}
