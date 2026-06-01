"""Generate the MCP reference landing page from the live tool registry.

The MCP server (, ADR-0023) registers twelve the documentation tools
plus a `sentinel.ping` health check. This generator imports the server
module's registry helper and renders a Starlight page so the docs site
reflects the tool surface without a separate hand-edit step.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Need both engine and the MCP server on sys.path for headless runs.
for member in ("engine", "packages/mcp-server/src", "packages/python-sdk/src"):
    sys.path.insert(0, str(REPO_ROOT / member))

from scripts.docs._common import (  # noqa: E402
    DOCS_CONTENT_ROOT,
    GENERATED_BANNER,
    render_frontmatter,
    write_if_changed,
)

OUTPUT = DOCS_CONTENT_ROOT / "mcp" / "index.md"

TOOL_DESCRIPTIONS: dict[str, str] = {
    "sentinel.ping": "Health check; returns server version + protocol version.",
    "sentinel.discover": "Crawl + map the target app.",
    "sentinel.plan": "Build a deterministic test plan from a discovery payload.",
    "sentinel.generate_tests": "Generate Playwright specs from a plan.",
    "sentinel.run_tests": "Drive the runner against generated/user specs.",
    "sentinel.audit": "End-to-end audit across every enabled module.",
    "sentinel.security_audit": "Run safe-security checks only.",
    "sentinel.performance_audit": "Run synthetic performance budgets only.",
    "sentinel.accessibility_audit": "Run accessibility checks only.",
    "sentinel.read_report": (
        "Read a top-level artifact under a run directory " "(path-traversal rejected, ≤ 256 KiB)."
    ),
    "sentinel.explain_failure": "Return the Analyzer's categorization + hypothesis for a failure.",
    "sentinel.suggest_fix": "Return Healer proposals + module recommendations for a finding.",
    "sentinel.verify_fix": (
        "Re-run a prior audit and return "
        "`fix_verified` / `partial` / `regressed` / `still_failing`."
    ),
}


def _collect_tool_names() -> list[str]:
    try:
        tools_pkg = importlib.import_module("sentinelqa_mcp.tools")
    except ImportError as exc:  # pragma: no cover — surfaced as freshness fail in CI
        raise RuntimeError(
            "sentinelqa_mcp.tools could not be imported; ensure the workspace is installed."
        ) from exc

    toolset_cls = getattr(tools_pkg, "SentinelToolset", None)
    if toolset_cls is not None and hasattr(toolset_cls, "with_defaults"):
        toolset = toolset_cls.with_defaults()
        return sorted(toolset.names())

    # Fallback: scan the tools package directory.
    pkg_dir = Path(next(iter(tools_pkg.__path__)))
    names: set[str] = set()
    for entry in sorted(pkg_dir.iterdir()):
        if entry.name.startswith("_") or entry.suffix != ".py":
            continue
        names.add(f"sentinel.{entry.stem}")
    names.add("sentinel.ping")
    return sorted(names)


def _render_tool_table(tool_names: list[str]) -> str:
    rows = ["| Tool | Description |", "|---|---|"]
    for name in tool_names:
        desc = TOOL_DESCRIPTIONS.get(name, "(no description — update gen_mcp_reference.py)")
        rows.append(f"| `{name}` | {desc} |")
    return "\n".join(rows)


def render() -> str:
    tool_names = _collect_tool_names()

    parts = [
        render_frontmatter(
            title="MCP reference",
            description="Tools surfaced by the SentinelQA MCP server.",
        ),
        GENERATED_BANNER.format(generator="gen_mcp_reference", target="docs-gen-mcp"),
        "",
        "The SentinelQA MCP server speaks JSON-RPC 2.0 over NDJSON-framed "
        "stdio at protocol `2024-11-05`. Every tool surfaces SentinelQA's "
        "agent-facing operations (the documentation) plus a health check. The wire "
        "envelope (`schema_version`, `tool`, `result`, `errors`, "
        "`evidence_refs`) is locked at "
        "[`packages/shared-schema/agent-envelope.schema.json`](https://github.com/Ohswedd/sentinelqa/blob/main/packages/shared-schema/agent-envelope.schema.json).",
        "",
        "## Running the server",
        "",
        "```bash",
        "uv run sentinel mcp --stdio",
        "uv run sentinel mcp --http 7331    # loopback-only; refuses non-loopback bind",
        "```",
        "",
        "Logs go to stderr. Stdout is reserved for MCP wire bytes "
        ". The HTTP transport never binds to a non-loopback "
        "address and exits 4 if asked to.",
        "",
        "## Tools",
        "",
        _render_tool_table(tool_names),
        "",
        "## Safety contract",
        "",
        "Every URL-bearing tool runs `SafetyPolicy.enforce` before any SDK "
        "call. Unsafe targets surface as envelope errors with "
        "`code=UNSAFE_TARGET` and `exit_code=4`. Destructive checks "
        "require the loaded config to opt in **and** to supply a valid "
        "`target.proof_of_authorization` (our engineering rules, ADR-0023).",
        "",
        "See `tests/security/test_mcp_safety.py` for the AST guard that "
        "enforces this on every CI pass.",
        "",
        "## Example client",
        "",
        "A Claude-Desktop-ready configuration ships under "
        "[`examples/mcp-claude-desktop/`]"
        "(https://github.com/Ohswedd/sentinelqa/tree/main/examples/mcp-claude-desktop)."
        " Drop it into Claude Desktop's MCP config to expose SentinelQA "
        "as an agent tool.",
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    content = render()
    changed = write_if_changed(OUTPUT, content)
    sys.stdout.write(f"{'updated' if changed else 'unchanged'}: {OUTPUT.relative_to(REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
