"""Generate the SDK reference landing page from the committed API snapshot.

The Python SDK's public surface is locked at
``packages/python-sdk/api-snapshot.json`` (, ADR-0021). This
generator reads the snapshot and renders a Starlight page so the docs
site reflects the SDK surface without a separate hand-edit step.

For mkdocstrings / pdoc-style full API docs we link out to the
``packages/python-sdk/README.md`` and the snapshot file; rendering
every signature inline would duplicate the snapshot bytes.
"""

from __future__ import annotations

import json
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

SNAPSHOT = REPO_ROOT / "packages" / "python-sdk" / "api-snapshot.json"
OUTPUT = DOCS_CONTENT_ROOT / "sdk" / "index.md"


_KIND_LABEL = {
    "class": "class",
    "function": "function",
    "constant": "constant",
    "exception": "exception",
    "module": "submodule",
    "alias": "alias",
}


def _render_module(name: str, members: dict[str, dict[str, object]]) -> str:
    lines = [f"### `{name}`", ""]
    if not members:
        lines.append("_(no public members at this revision)_")
        lines.append("")
        return "\n".join(lines)

    lines.append("| Name | Kind |")
    lines.append("|---|---|")
    for member_name in sorted(members):
        entry = members[member_name]
        kind = str(entry.get("kind", "")) if isinstance(entry, dict) else ""
        label = _KIND_LABEL.get(kind, kind or "—")
        lines.append(f"| `{member_name}` | {label} |")
    lines.append("")
    return "\n".join(lines)


def render() -> str:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    if not isinstance(snapshot, dict) or "modules" not in snapshot:
        raise RuntimeError(
            "unexpected api-snapshot.json shape — top-level `modules` key missing; "
            "update gen_sdk_reference.py to match."
        )
    modules: dict[str, dict[str, dict[str, object]]] = snapshot["modules"]

    sections = [_render_module(name, modules[name]) for name in sorted(modules)]

    parts = [
        render_frontmatter(
            title="Python SDK",
            description="Public surface of the `sentinelqa` Python package.",
        ),
        GENERATED_BANNER.format(generator="gen_sdk_reference", target="docs-gen-sdk"),
        "",
        "The `sentinelqa` package exposes a small, stable surface: the "
        "`Sentinel` facade (sync + async), the typed result models, the "
        "error hierarchy, and the agent-message serialiser. The public "
        "surface is locked by an API snapshot — breaking changes require "
        "an ADR + a deprecation window (Phase 16 deprecation policy).",
        "",
        "## Quickstart",
        "",
        "```python",
        "from sentinelqa import Sentinel",
        "",
        "sentinel = Sentinel.from_config_file('sentinel.config.yaml')",
        "result = sentinel.audit()",
        "",
        "if not result.passed:",
        "    for blocker in result.blockers:",
        "        print(blocker.title, blocker.recommendation)",
        "```",
        "",
        "Async parity is available for every public method:",
        "",
        "```python",
        "result = await sentinel.async_audit()",
        "```",
        "",
        "## Modules",
        "",
        "The following modules constitute the public surface. The exact "
        "member list below is generated from "
        "`packages/python-sdk/api-snapshot.json`.",
        "",
        "\n".join(sections),
        "## Agent messages",
        "",
        "Every public exception, every `Finding`, every `RepairSuggestion`, "
        "and `AuditResult.to_agent_messages()` produce stable, redacted "
        "dicts versioned by `AGENT_MESSAGE_SCHEMA_VERSION`. Use "
        "`sentinelqa.agent.format(messages, format='ndjson')` for a "
        "deterministic byte-stable stream.",
        "",
        "## Stability",
        "",
        "- Adding members never breaks; removing or renaming requires an ADR.",
        "- The snapshot is regenerated via `make sdk-api-snapshot`.",
        "- `tests/unit/sdk/test_api_snapshot.py` fails on every CI pass if "
        "the snapshot drifts from a fresh dump.",
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    content = render()
    changed = write_if_changed(OUTPUT, content)
    sys.stdout.write(f"{'updated' if changed else 'unchanged'}: {OUTPUT.relative_to(REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
