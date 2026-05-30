"""Generate the CLI reference page with per-command status sourced from
``plans/STATUS.md``.

Task 27.03 demands that the CLI reference accurately reflects which
commands are implemented vs. registered-stubs at the time the doc-site
is built. The source of truth is ``plans/STATUS.md`` (the live phase
tracker). This generator parses STATUS to derive implemented commands,
falls back to the static registry below for fully-stubbed commands, and
writes ``apps/docs/src/content/docs/cli/index.md``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.docs._common import (  # noqa: E402
    DOCS_CONTENT_ROOT,
    GENERATED_BANNER,
    render_frontmatter,
    write_if_changed,
)

STATUS_PATH = REPO_ROOT / "plans" / "STATUS.md"
OUTPUT = DOCS_CONTENT_ROOT / "cli" / "index.md"

# The PRD §13.1 contract: every command SentinelQA will ship. Status is
# `stub` by default; `implemented` is upgraded by the STATUS.md scan
# below when the phase that ships the command is marked `[x]`.
# Keep the order matching PRD §13.1.
COMMANDS: list[tuple[str, str, int]] = [
    ("init", "Initialize a new SentinelQA project", 2),
    ("doctor", "Diagnose the local environment", 2),
    ("discover", "Crawl + map the target app", 5),
    ("plan", "Generate a deterministic test plan", 6),
    ("generate", "Generate Playwright specs from a plan", 7),
    ("test", "Run generated/user specs (raw runner)", 8),
    ("audit", "End-to-end audit (discovery → planner → … → reports)", 2),
    ("functional", "Run functional-module specs only", 10),
    ("a11y", "Run accessibility-module checks", 11),
    ("perf", "Run performance-module checks", 12),
    ("security", "Run safe-security-module checks", 13),
    ("api", "Run API contract / negative / auth / pagination", 22),
    ("visual", "Visual regression: diff / accept / capture", 21),
    ("chaos", "Bounded adversarial scenarios", 23),
    ("llm-audit", "LLM-Code anti-pattern detectors", 19),
    ("fix", "Healer / self-repair proposals", 20),
    ("ci", "CI-mode dispatch with diff-aware selection", 17),
    ("report", "Re-render reports for a prior run", 15),
    ("plugins", "List / inspect / validate installed plugins", 24),
    ("mcp", "Run the MCP server (stdio default)", 18),
]

CMD_DETAIL: dict[str, str] = {
    "init": "Idempotent project initializer. Writes `sentinel.config.yaml`, "
    "the bundled GitHub workflow under `.github/workflows/sentinel.yml`, and "
    "an empty `.sentinel/` artifact directory. `--force` overwrites existing files.",
    "doctor": "Validates Python / Node / Playwright / config / safety / "
    "reachability / env / `.sentinel` writable / disk. ASCII or single-line JSON output. "
    "See [Doctor reference](/get-started/doctor/).",
    "discover": "HTTP-first crawler with optional Playwright backend. Writes "
    "`discovery.json` + `forms.json` + `api.json` + `auth.json` + `risk.json` + "
    "`discovery.report.md`. See [Discovery module](/modules/discovery/).",
    "plan": "Deterministic-first planner with optional LLM adapter. "
    "Writes `plan.json` (byte-stable) + `plan.md`. See [Planner](/modules/planner/).",
    "generate": "Jinja2-driven Playwright spec generator with semantic locators. "
    "Banner-protected against hand edits. See [Generator](/modules/generator/).",
    "test": "Direct dispatch to the local or Docker runner. Sharding, retries, "
    "quarantine. See [Runner](/modules/runner/).",
    "audit": "Drives the canonical 17-step run lifecycle end-to-end across every "
    "enabled module. The default entry point for CI.",
    "functional": "Walks `tests/sentinel/` for `*.spec.ts`, drives the runner, "
    "translates failed executions into findings. See [Functional](/modules/functional/).",
    "a11y": "Per-route axe-core + keyboard / landmark / sr-name checks. Always "
    'phrases findings as "Automated accessibility check…". See '
    "[Accessibility](/modules/accessibility/).",
    "perf": "Synthetic page / API / CPU / leak budgets. Always labels findings "
    "synthetic. See [Performance](/modules/performance/).",
    "security": "Safe-by-default HTTP checks; gated destructive probes; dep + "
    "SAST adapters. See [Security](/modules/security/).",
    "api": "OpenAPI / GraphQL contract, negative cases, auth matrix, pagination, "
    "error-shape, backward-compat. See [API](/modules/api/).",
    "visual": "Pillow diff with SSIM filter. Hard CI-acceptance guard. See "
    "[Visual](/modules/visual/).",
    "chaos": "Bounded Playwright-injected scenarios. See [Chaos](/modules/chaos/).",
    "llm-audit": "Sixteen detectors for LLM-generated app anti-patterns. See "
    "[LLM-Code Audit](/modules/llm-audit/).",
    "fix": "Locator / wait / fixture repair proposals. Banner-aware apply, "
    "assertion-weakening guard. See [Healer](/modules/healer/).",
    "ci": "Resolves PRD §21.3 presets (`fast` / `standard` / `full` / `nightly` / "
    "`release`); diff-aware selection. See [CI/CD](/cicd/).",
    "report": "Re-renders persisted artifacts to `html` / `json` / `sarif` / "
    "`junit` / `md`. Idempotent. `--explain-score` prints the score derivation.",
    "plugins": "Lists / inspects / validates installed plugins. See [Plugins](/plugins/).",
    "mcp": "Runs the MCP server (NDJSON-framed JSON-RPC over stdio, or "
    "loopback-only HTTP). Twelve `sentinel.*` tools. See [MCP](/mcp/).",
}


def _implemented_phases(status_text: str) -> set[int]:
    done: set[int] = set()
    for match in re.finditer(r"^- \[x\] Phase (\d{2}) ", status_text, flags=re.MULTILINE):
        done.add(int(match.group(1)))
    return done


def _render_table(implemented: set[int]) -> str:
    rows = ["| Command | Status | Phase | Description |", "|---|---|---:|---|"]
    for name, desc, phase in COMMANDS:
        status = "Stable" if phase in implemented else "Planned"
        rows.append(f"| `sentinel {name}` | `{status}` | {phase:02d} | {desc} |")
    return "\n".join(rows)


def _render_details() -> str:
    sections: list[str] = []
    for name, _desc, _phase in COMMANDS:
        anchor = name.replace(" ", "-")
        sections.append(f"### `sentinel {name}` {{#sentinel-{anchor}}}")
        sections.append("")
        sections.append(CMD_DETAIL[name])
        sections.append("")
    return "\n".join(sections)


def render() -> str:
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    implemented = _implemented_phases(status_text)

    parts = [
        render_frontmatter(
            title="CLI reference",
            description=(
                "Every `sentinel` command, with its implementation status "
                "sourced from plans/STATUS.md."
            ),
        ),
        GENERATED_BANNER.format(generator="gen_cli_status", target="docs-gen-cli"),
        "",
        "SentinelQA's CLI surface is defined in PRD §13.1 and stays the "
        "same across phases — commands are registered at all times so "
        "`sentinel --help` always lists the full contract. The **Status** "
        "column below is sourced from `plans/STATUS.md` and updates as "
        "phases land.",
        "",
        "All commands honor the global flags in PRD §13.3: `--config`, "
        "`--json`, `--verbose`, `--quiet`, `--ci`, `--url`, `--output`, "
        "`--fail-under`, `--dry-run`. Exit codes follow the canonical "
        "grid in [Error codes](/errors/).",
        "",
        "## Command status",
        "",
        _render_table(implemented),
        "",
        "## Command reference",
        "",
        _render_details(),
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    content = render()
    changed = write_if_changed(OUTPUT, content)
    sys.stdout.write(f"{'updated' if changed else 'unchanged'}: {OUTPUT.relative_to(REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
