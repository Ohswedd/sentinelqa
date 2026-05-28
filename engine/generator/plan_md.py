"""sentinel.generated.plan.md emitter (task 07.05).

Produces a human-readable Markdown summary of the generation pass that
reviewers can scan in PR diff comments. The file lands at
``tests/sentinel/sentinel.generated.plan.md`` and a copy in the current
run directory. If a prior plan.md exists, we render a small diff
section so reviewers can see which specs were added / removed since
the last generation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from engine.domain.flow import Flow

PLAN_FILE_NAME: str = "sentinel.generated.plan.md"


@dataclass(frozen=True)
class GeneratedPlanInputs:
    """Inputs the plan-md renderer needs from the pipeline."""

    plan_id: str
    run_id: str
    target_url: str
    flows: Sequence[Flow]
    spec_paths: Sequence[Path]
    page_object_paths: Sequence[Path]
    fixture_paths: Sequence[Path]
    audit_warnings: int = 0
    prior_spec_paths: Sequence[Path] = field(default_factory=tuple)


def render_generated_plan_md(inputs: GeneratedPlanInputs) -> str:
    """Return the Markdown body. Output is deterministic for given inputs."""

    lines: list[str] = []
    lines.append("<!-- SentinelQA Generated — do not edit by hand. -->")
    lines.append(
        "<!-- Re-run `sentinel generate` to regenerate; manual edits will be overwritten. -->"
    )
    lines.append("")
    lines.append("# SentinelQA — generated plan")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Plan ID: `{inputs.plan_id}`")
    lines.append(f"- Run ID: `{inputs.run_id}`")
    lines.append(f"- Target: `{inputs.target_url}`")
    lines.append(f"- Specs generated: **{len(inputs.spec_paths)}**")
    lines.append(f"- Page objects generated: **{len(inputs.page_object_paths)}**")
    lines.append(f"- Fixtures generated: **{len(inputs.fixture_paths)}**")
    lines.append(f"- Brittleness audit warnings: **{inputs.audit_warnings}**")
    lines.append("")

    lines.append("## Flows")
    lines.append("")
    if not inputs.flows:
        lines.append("_No flows in the plan._")
    else:
        lines.append("| Priority | Source | Confidence | Extractor | Name |")
        lines.append("|---|---|---:|---|---|")
        for flow in sorted(inputs.flows, key=lambda f: (f.priority, f.name, f.id)):
            lines.append(
                f"| {flow.priority} | {flow.source} | {flow.confidence:.2f} | "
                f"`{flow.extractor or '-'}` | {flow.name} |"
            )
    lines.append("")

    lines.append("## Files")
    lines.append("")
    if inputs.spec_paths:
        lines.append("### Specs")
        lines.append("")
        for path in sorted(inputs.spec_paths, key=lambda p: p.as_posix()):
            lines.append(f"- `{path.as_posix()}`")
        lines.append("")
    if inputs.page_object_paths:
        lines.append("### Page objects")
        lines.append("")
        for path in sorted(inputs.page_object_paths, key=lambda p: p.as_posix()):
            lines.append(f"- `{path.as_posix()}`")
        lines.append("")
    if inputs.fixture_paths:
        lines.append("### Fixtures")
        lines.append("")
        for path in sorted(inputs.fixture_paths, key=lambda p: p.as_posix()):
            lines.append(f"- `{path.as_posix()}`")
        lines.append("")

    if inputs.prior_spec_paths:
        diff = _render_diff(prior=inputs.prior_spec_paths, current=inputs.spec_paths)
        if diff:
            lines.append("## Diff vs previous generation")
            lines.append("")
            lines.extend(diff)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_diff(*, prior: Sequence[Path], current: Sequence[Path]) -> list[str]:
    prior_set = {p.as_posix() for p in prior}
    current_set = {p.as_posix() for p in current}
    added = sorted(current_set - prior_set)
    removed = sorted(prior_set - current_set)
    if not added and not removed:
        return ["_No changes vs previous generation._"]
    out: list[str] = []
    if added:
        out.append("### Added")
        out.append("")
        for path in added:
            out.append(f"- `{path}`")
        out.append("")
    if removed:
        out.append("### Removed")
        out.append("")
        for path in removed:
            out.append(f"- `{path}`")
    return out


def read_prior_spec_paths(plan_md_path: Path) -> list[Path]:
    """Parse ``tests/sentinel/sentinel.generated.plan.md`` for the spec list.

    Best-effort: we look for the ``### Specs`` section and read until
    the next heading. Lines that look like list items pointing at .ts
    files become :class:`Path` entries. Returns an empty list if the
    file does not exist or the section is missing.
    """

    if not plan_md_path.exists():
        return []
    try:
        text = plan_md_path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[Path] = []
    in_specs = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("### "):
            in_specs = line == "### Specs"
            continue
        if line.startswith("## "):
            in_specs = False
            continue
        if not in_specs:
            continue
        if line.startswith("- `") and line.endswith("`"):
            inner = line[3:-1]
            out.append(Path(inner))
    return out


__all__ = [
    "GeneratedPlanInputs",
    "PLAN_FILE_NAME",
    "read_prior_spec_paths",
    "render_generated_plan_md",
]
