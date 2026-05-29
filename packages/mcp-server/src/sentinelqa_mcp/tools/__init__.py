"""Tool registry + base contract for MCP tools (ADR-0023, task 18.02).

Each tool ships in its own module and registers itself by name with a
:class:`SentinelToolset`. The base :class:`Tool` Protocol enforces:

- A name matching ``sentinel.<lower_snake>`` (PRD §16.1).
- A JSON Schema describing the arguments.
- An ``invoke`` coroutine that returns an :class:`AgentEnvelope`.

URL-bearing tools run the Phase-01 :class:`SafetyPolicy` *before* any
SDK call. The check is enforced both per-tool (so blocked targets
return a clean error envelope) and at the test layer
(``tests/security/test_mcp_safety.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from sentinelqa_mcp.envelope import AgentEnvelope
from sentinelqa_mcp.protocol import ToolSpec

if TYPE_CHECKING:
    from sentinelqa import Sentinel


@dataclass(frozen=True)
class ToolContext:
    """Shared per-server context passed to every tool ``invoke``.

    Tools never reach for global state — they receive ``sentinel`` (the
    Phase-16 SDK instance), ``project_path`` (the working tree root), and
    a per-call ``extras`` map for plumbing (e.g. tests injecting a stub
    runner).
    """

    sentinel: Sentinel
    project_path: Path
    extras: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    """A single MCP tool implementation."""

    @property
    def spec(self) -> ToolSpec: ...

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope: ...


class SentinelToolset:
    """Registry of MCP tools — the source-of-truth list returned by ``tools/list``.

    ``with_defaults`` builds the production registry containing the
    twelve PRD §16 tools plus ``sentinel.ping``. Tests can construct
    empty registries and selectively register stubs.
    """

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if name in self._tools:
            raise ValueError(f"Tool {name!r} already registered")
        self._tools[name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def list_specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools[name].spec for name in self.names())

    def __iter__(self) -> Iterator[Tool]:
        for name in self.names():
            yield self._tools[name]

    def __len__(self) -> int:
        return len(self._tools)

    @classmethod
    def with_defaults(cls) -> SentinelToolset:
        """Construct the canonical PRD §16 registry (plus ``sentinel.ping``)."""

        from sentinelqa_mcp.tools.accessibility_audit import AccessibilityAuditTool
        from sentinelqa_mcp.tools.audit import AuditTool
        from sentinelqa_mcp.tools.discover import DiscoverTool
        from sentinelqa_mcp.tools.explain_failure import ExplainFailureTool
        from sentinelqa_mcp.tools.generate_tests import GenerateTestsTool
        from sentinelqa_mcp.tools.performance_audit import PerformanceAuditTool
        from sentinelqa_mcp.tools.ping import PingTool
        from sentinelqa_mcp.tools.plan import PlanTool
        from sentinelqa_mcp.tools.read_report import ReadReportTool
        from sentinelqa_mcp.tools.run_tests import RunTestsTool
        from sentinelqa_mcp.tools.security_audit import SecurityAuditTool
        from sentinelqa_mcp.tools.suggest_fix import SuggestFixTool
        from sentinelqa_mcp.tools.verify_fix import VerifyFixTool

        return cls(
            tools=(
                PingTool(),
                DiscoverTool(),
                PlanTool(),
                GenerateTestsTool(),
                RunTestsTool(),
                AuditTool(),
                SecurityAuditTool(),
                PerformanceAuditTool(),
                AccessibilityAuditTool(),
                ReadReportTool(),
                ExplainFailureTool(),
                SuggestFixTool(),
                VerifyFixTool(),
            )
        )


__all__ = ["SentinelToolset", "Tool", "ToolContext"]
