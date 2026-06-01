"""Planner writer (task 06.03, the documentation + §20.1).

Emits two artifacts per run:

- ``plan.json`` — byte-stable JSON of the :class:`TestPlan` plus its
  ``schema_version`` envelope.
- ``plan.md`` — deterministic human-readable summary suitable for PR
  comments and CI logs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from engine.domain.flow import Flow
from engine.domain.schema import CONFIG_SCHEMA_VERSION
from engine.domain.test_plan import TestPlan


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str | int | bool | float):
        return value
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set | frozenset):
        # Sets are unordered; sort the serialized members so plan.json is
        # byte-stable across runs (PYTHONHASHSEED otherwise leaks).
        items = [_to_jsonable(item) for item in value]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable(asdict(value))
    return str(value)


def _dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def write_plan_artifacts(
    *,
    plan: TestPlan,
    out_dir: Path,
) -> dict[str, Path]:
    """Write ``plan.json`` and ``plan.md`` into ``out_dir``. Return the paths."""

    plan_json_path = out_dir / "plan.json"
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "plan": _to_jsonable(plan),
    }
    _dump(plan_json_path, payload)

    plan_md_path = out_dir / "plan.md"
    plan_md_path.write_text(_render_markdown(plan), encoding="utf-8")
    return {"plan_json": plan_json_path, "plan_md": plan_md_path}


def read_plan(plan_json_path: Path) -> TestPlan:
    """Re-parse a ``plan.json`` file back into a :class:`TestPlan`.

    Used both by the runner (Phase 08+) and by the round-trip test guards.
    """

    payload = json.loads(plan_json_path.read_text(encoding="utf-8"))
    plan_payload = payload.get("plan")
    if plan_payload is None:
        raise ValueError(f"{plan_json_path}: missing 'plan' key — file is not a SentinelQA plan.")
    return TestPlan.model_validate(plan_payload)


def _render_markdown(plan: TestPlan) -> str:
    lines: list[str] = []
    lines.append("# Test plan")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Plan ID: `{plan.id}`")
    lines.append(f"- Run ID: `{plan.run_id}`")
    lines.append(f"- Discovery graph: `{plan.discovery_graph_id}`")
    lines.append(f"- Risk map: `{plan.risk_map_id}`")
    lines.append(f"- Target: `{plan.target_url}`")
    lines.append(f"- Flows: **{len(plan.flows)}**")
    lines.append(f"- Test cases: **{len(plan.test_cases)}**")
    lines.append("")

    lines.append("## Coverage estimate")
    lines.append("")
    by_module = plan.coverage_estimate.by_module
    if not by_module:
        lines.append("_No test cases planned._")
    else:
        lines.append("| Module | Test cases |")
        lines.append("|---|---:|")
        for module, count in sorted(by_module.items()):
            lines.append(f"| {module} | {count} |")
        lines.append(f"| **total** | **{plan.coverage_estimate.total}** |")
    lines.append("")

    lines.append("## Flows by priority")
    lines.append("")
    if not plan.flows:
        lines.append("_No flows planned._")
    else:
        by_priority: dict[str, list[Flow]] = {}
        for flow in plan.flows:
            by_priority.setdefault(flow.priority, []).append(flow)
        for priority in sorted(by_priority):
            flows = by_priority[priority]
            lines.append(f"### {priority} — {len(flows)} flow(s)")
            lines.append("")
            lines.append("| Risk | Source | Conf. | Extractor | Name |")
            lines.append("|---|---|---:|---|---|")
            for flow in flows:
                lines.append(
                    f"| {flow.risk} | {flow.source} | {flow.confidence:.2f} | "
                    f"`{flow.extractor or '-'}` | {flow.name} |"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["read_plan", "write_plan_artifacts"]
