"""``sentinel.read_report`` — fetch a persisted artifact from a run dir."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sentinelqa_mcp.envelope import AgentEnvelope, success
from sentinelqa_mcp.errors import ToolError
from sentinelqa_mcp.protocol import ToolSpec
from sentinelqa_mcp.tools import ToolContext

_MAX_BYTES: int = 256 * 1024


class ReadReportTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sentinel.read_report",
            description=(
                "Read a file from a SentinelQA run directory. Pass `run_id` "
                "(or `latest=true`) to pick the run, and `path` to pick the "
                "artifact (e.g. 'run.json', 'findings.json'). Files larger "
                f"than {_MAX_BYTES} bytes are truncated."
            ),
            inputSchema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string"},
                    "latest": {"type": "boolean", "default": False},
                    "path": {"type": "string", "default": "run.json"},
                },
            },
            **{"_meta": {"read_only": True}},
        )

    async def invoke(self, arguments: Mapping[str, Any], context: ToolContext) -> AgentEnvelope:
        run_id = arguments.get("run_id")
        latest = bool(arguments.get("latest", False))
        rel_path = str(arguments.get("path") or "run.json")
        if "/" in rel_path or "\\" in rel_path or rel_path.startswith(".."):
            raise ToolError(
                "E-CFG-002",
                "`path` must be a single filename inside the run directory.",
                exit_code=2,
                suggested_fix="Pass a top-level artifact name like 'run.json'.",
            )
        run_dir: Path = await context.sentinel.async_report(
            run_id=run_id if isinstance(run_id, str) else None,
            latest=latest or run_id is None,
        )
        target = run_dir / rel_path
        if not target.is_file():
            raise ToolError(
                "E-FILE-001",
                f"Artifact {rel_path!r} not found in {run_dir.name}",
                exit_code=3,
                suggested_fix="Call sentinel.audit first, or pass a different `path`.",
            )
        raw = target.read_bytes()
        truncated = False
        if len(raw) > _MAX_BYTES:
            raw = raw[:_MAX_BYTES]
            truncated = True
        try:
            content_text = raw.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content_text = raw.hex()
            encoding = "hex"
        payload = {
            "run_id": run_dir.name,
            "path": rel_path,
            "encoding": encoding,
            "truncated": truncated,
            "byte_count": len(raw),
            "content": content_text,
        }
        return success("sentinel.read_report", payload, evidence_refs=(target.name,))


__all__ = ["ReadReportTool"]
