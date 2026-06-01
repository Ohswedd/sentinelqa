"""Generate the SentinelQA error-code reference page.

Reads :mod:`engine.errors.codes` (the single source of truth, registered
in and frozen for the CLI exit-code contract) and writes the
Starlight page at ``apps/docs/src/content/docs/errors/index.md``.

Wired into ``make docs-gen-error-codes`` and exercised by
``tests/integration/docs/test_generated_docs_fresh.py``.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Add the engine package to sys.path so this script runs without `uv` setup.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "engine"))

from engine.errors.codes import (  # noqa: E402
    ERROR_REGISTRY,
    EXIT_CONFIG_ERROR,
    EXIT_DEPENDENCY_MISSING,
    EXIT_INTERNAL_ERROR,
    EXIT_QUALITY_GATE_FAILED,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_TEST_EXECUTION_FAILED,
    EXIT_UNSAFE_TARGET,
)
from scripts.docs._common import (  # noqa: E402
    DOCS_CONTENT_ROOT,
    GENERATED_BANNER,
    render_frontmatter,
    write_if_changed,
)

OUTPUT = DOCS_CONTENT_ROOT / "errors" / "index.md"

EXIT_CODES: list[tuple[int, str, str]] = [
    (EXIT_SUCCESS, "Success", "The audit completed without quality-gate failures."),
    (
        EXIT_QUALITY_GATE_FAILED,
        "Quality gate failed",
        "Findings or score crossed a configured policy threshold.",
    ),
    (
        EXIT_CONFIG_ERROR,
        "Invalid config",
        (
            "`sentinel.config.yaml` failed schema validation, or the CLI "
            "was invoked with incompatible options."
        ),
    ),
    (
        EXIT_RUNTIME_ERROR,
        "Runtime error",
        "An unexpected runtime error occurred (network unreachable, disk full, etc.).",
    ),
    (
        EXIT_UNSAFE_TARGET,
        "Unsafe target",
        (
            "The resolved target was not local and not on the allow-list, "
            "or a destructive mode was requested without a valid "
            "proof-of-authorization."
        ),
    ),
    (
        EXIT_DEPENDENCY_MISSING,
        "Dependency missing",
        "A required binary (Node, pnpm, Playwright, `sentinel-ts`) was not found.",
    ),
    (
        EXIT_TEST_EXECUTION_FAILED,
        "Test execution failed",
        "The runner crashed or could not complete the planned tests.",
    ),
    (EXIT_INTERNAL_ERROR, "Internal error", "Bug in SentinelQA itself; file an issue."),
]


def _render_exit_table() -> str:
    rows = ["| Code | Name | Meaning |", "|---:|---|---|"]
    for code, name, meaning in EXIT_CODES:
        rows.append(f"| {code} | {name} | {meaning} |")
    return "\n".join(rows)


def _render_error_groups() -> str:
    groups: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
    for spec in ERROR_REGISTRY.values():
        groups[spec.exit_code].append((spec.code, spec.message_template, spec.suggested_fix))

    lookup = {code: name for code, name, _meaning in EXIT_CODES}

    sections: list[str] = []
    for exit_code in sorted(groups):
        sections.append(f"## Exit {exit_code} — {lookup[exit_code]}\n")
        sections.append("| Code | Message template | Suggested fix |")
        sections.append("|---|---|---|")
        for code, template, fix in sorted(groups[exit_code]):
            tpl_cell = template.replace("|", "\\|")
            fix_cell = fix.replace("|", "\\|")
            sections.append(f"| `{code}` | {tpl_cell} | {fix_cell} |")
        sections.append("")
    return "\n".join(sections)


def render() -> str:
    parts = [
        render_frontmatter(
            title="Error codes",
            description="CLI exit codes and structured error codes raised by SentinelQA.",
        ),
        GENERATED_BANNER.format(generator="gen_error_codes", target="docs-gen-error-codes"),
        "",
        "SentinelQA's CLI exits with a fixed code grid (the documentation / "
        "our engineering rules). Structured error codes are emitted via the "
        "agent-message contract and surfaced in `audit.log`.",
        "",
        "## CLI exit codes",
        "",
        _render_exit_table(),
        "",
        "## Structured error codes",
        "",
        "Each code below maps to one of the CLI exit codes above. The "
        "message template uses Python `str.format` placeholders; the "
        "actual values are interpolated at raise time.",
        "",
        _render_error_groups(),
    ]
    return "\n".join(parts) + ("" if parts[-1].endswith("\n") else "\n")


def main() -> int:
    content = render()
    changed = write_if_changed(OUTPUT, content)
    sys.stdout.write(f"{'updated' if changed else 'unchanged'}: {OUTPUT.relative_to(REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
