"""— sentinel.verify_fix end-to-end fixture loop.

The agent applies a fix; the MCP tool re-runs the audit, diffs prior
findings against the new findings, and reports a four-valued decision
(fix_verified / partial / regressed / still_failing).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest
from engine.orchestrator.registry import default_registry

from sentinelqa_mcp import MCPServer as MCPServerClass


@pytest.fixture
def server_with_findings_state(
    server: MCPServerClass,
) -> tuple[MCPServerClass, _Stub]:
    """Wire a functional stub that emits a controllable finding set."""

    reg = default_registry()
    prior: Any = reg.modules.pop("functional", None)
    stub = _Stub()
    reg.register_module("functional", stub)
    try:
        yield server, stub
    finally:
        reg.modules.pop("functional", None)
        if prior is not None:
            reg.register_module("functional", prior)


async def _call(server: MCPServerClass, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = await server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    parsed: dict[str, Any] = json.loads(response["result"]["content"][0]["text"])
    return parsed


async def test_verify_fix_reports_fix_verified_when_finding_cleared(
    server_with_findings_state: tuple[MCPServerClass, _Stub],
) -> None:
    server, stub = server_with_findings_state
    stub.next_findings = ({"title": "bad cookie", "module": "functional"},)
    first = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    assert first["errors"] == [], first
    first_run_id = first["result"]["run_id"]
    # The synthetic finding is recorded; clear it.
    stub.next_findings = ()
    verify = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": first_run_id, "finding_id": _first_finding_id(first)},
    )
    assert verify["result"]["decision"] == "fix_verified"
    assert verify["result"]["regression_finding_ids"] == []


async def test_verify_fix_reports_still_failing(
    server_with_findings_state: tuple[MCPServerClass, _Stub],
) -> None:
    server, stub = server_with_findings_state
    stub.next_findings = ({"title": "bad cookie", "module": "functional"},)
    first = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    # Same finding stays.
    verify = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": first["result"]["run_id"], "finding_id": _first_finding_id(first)},
    )
    assert verify["result"]["decision"] == "still_failing"
    assert verify["result"]["fixed_finding_ids"] == []


async def test_verify_fix_reports_regressed(
    server_with_findings_state: tuple[MCPServerClass, _Stub],
) -> None:
    server, stub = server_with_findings_state
    stub.next_findings = ({"title": "bad cookie", "module": "functional"},)
    first = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    stub.next_findings = (
        {"title": "bad cookie", "module": "functional"},
        {"title": "new regression", "module": "functional"},
    )
    verify = await _call(
        server,
        "sentinel.verify_fix",
        {"run_id": first["result"]["run_id"], "finding_id": _first_finding_id(first)},
    )
    assert verify["result"]["decision"] == "regressed"
    assert verify["result"]["regression_finding_ids"]


async def test_verify_fix_reports_partial_when_target_cleared_but_unchanged_findings(
    server_with_findings_state: tuple[MCPServerClass, _Stub],
) -> None:
    server, stub = server_with_findings_state
    stub.next_findings = (
        {"title": "bad cookie", "module": "functional"},
        {"title": "missing csp", "module": "functional"},
    )
    first = await _call(server, "sentinel.audit", {"url": "http://localhost:3000"})
    # Clear the target only; the second finding lingers.
    stub.next_findings = ({"title": "missing csp", "module": "functional"},)
    verify = await _call(
        server,
        "sentinel.verify_fix",
        {
            "run_id": first["result"]["run_id"],
            "finding_id": _first_finding_id(first, title="bad cookie"),
        },
    )
    assert verify["result"]["decision"] == "partial"
    assert verify["result"]["unchanged_finding_ids"]


def _first_finding_id(envelope: dict[str, Any], *, title: str | None = None) -> str:
    findings = envelope["result"]["findings"]
    for f in findings:
        if title is None or f.get("title") == title:
            return str(f["id"])
    raise AssertionError(f"no finding matching title={title!r} in {findings!r}")


# ---------------------------------------------------------------------------
# Functional-module stub
# ---------------------------------------------------------------------------


class _Stub:
    """Factory that returns a fresh :class:`_StubModule` per audit call.

    Stored on the process-wide ModuleRegistry under the ``"functional"``
    key. Tests mutate :attr:`next_findings` between audits to drive the
    verify-fix decision matrix.
    """

    NAME: ClassVar[str] = "functional"

    def __init__(self) -> None:
        self.next_findings: tuple[dict[str, str], ...] = ()
        self.invocations: int = 0

    def __call__(self, config: Any, decision: Any) -> _StubModule:
        self.invocations += 1
        return _StubModule(config=config, decision=decision, owner=self)


class _StubModule:
    """Mimics the :class:`engine.modules.base.SentinelModule` surface enough
    to satisfy ``isinstance(result, SentinelModule)`` — but instead of
    fighting the seven-step lifecycle we override ``run`` directly to
    return a ModuleResult with the owner's synthetic findings.
    """

    name: ClassVar[str] = _Stub.NAME

    def __init__(self, *, config: Any, decision: Any, owner: _Stub) -> None:
        self._config = config
        self._decision = decision
        self._owner = owner

    def run(self, ctx: Any) -> Any:
        from datetime import UTC, datetime

        from engine.domain.finding import Finding, FindingLocation
        from engine.domain.module_result import ModuleResult

        findings: list[Finding] = []
        now = datetime.now(UTC)
        for entry in self._owner.next_findings:
            findings.append(
                Finding(
                    id=ctx.id_generator.new("FND"),
                    run_id=ctx.run_id,
                    module=entry["module"],
                    category="reliability",
                    severity="low",
                    confidence=0.9,
                    title=entry["title"],
                    description=entry["title"],
                    recommendation="Apply the documented remediation.",
                    suggested_fix=None,
                    affected_target=None,
                    evidence=(),
                    location=FindingLocation(route=None, selector=None, file=None, line=None),
                    created_at=now,
                )
            )
        return ModuleResult(
            id=ctx.id_generator.new("MOD"),
            name=self.name,
            status="passed" if not findings else "failed",
            findings=tuple(findings),
            metrics={},
            duration_ms=1,
            errors=(),
        )


# Make _StubModule register as a SentinelModule subclass so the orchestrator
# routes through it. We can't subclass SentinelModule directly without
# implementing every abstract method; instead we register the ABC vroom.
def _register_as_sentinel_module() -> None:
    from engine.modules.base import SentinelModule

    SentinelModule.register(_StubModule)


_register_as_sentinel_module()


# Make sure the test file is self-contained for pytest discovery.
def test_stub_module_self_check(tmp_path: Path) -> None:
    stub = _Stub()
    stub.next_findings = ({"title": "t", "module": "functional"},)
    assert stub.invocations == 0
