"""Generate the ADR index page for the docs site.

Reads ``docs/adr/`` and writes a Starlight-friendly index at
``apps/docs/src/content/docs/adrs/index.md``. Source of truth is the
heading + the `## Status` line of each ADR file; the markdown
``docs/adr/README.md`` is the canonical human index but is not parsed
here — keeping the generator tied directly to the ADR files means new
ADRs surface in the docs without a second edit.
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

ADR_DIR = REPO_ROOT / "docs" / "adr"
OUTPUT = DOCS_CONTENT_ROOT / "adrs" / "index.md"

TITLE_RE = re.compile(r"^# ADR-(\d{4}): (.+)$", re.MULTILINE)
STATUS_RE = re.compile(r"^## Status\s*\n+([^\n#]+)", re.MULTILINE)


def _adr_files() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


def _parse(adr: Path) -> tuple[str, str, str]:
    text = adr.read_text(encoding="utf-8")
    title_match = TITLE_RE.search(text)
    status_match = STATUS_RE.search(text)
    if not title_match or not status_match:
        raise RuntimeError(f"{adr.name}: missing title or status heading")
    number = title_match.group(1)
    title = title_match.group(2).strip()
    status = status_match.group(1).strip().split("|")[0].strip()
    # Some ADRs use `Proposed | Accepted | Superseded by ADR-NNNN | Deprecated`
    # as a literal selector line — normalize that to "Accepted" when the
    # registered status list survives (the actual status is one token).
    if status in {"Proposed", "Accepted", "Deprecated"} or status.startswith("Superseded"):
        normalized_status = status
    else:
        # Status line carries the registered status as the first non-bar token
        normalized_status = status.split()[0]
    return number, title, normalized_status


def render() -> str:
    rows = ["| ADR | Title | Status |", "|---|---|---|"]
    for adr in _adr_files():
        number, title, status = _parse(adr)
        link = f"https://github.com/Ohswedd/sentinelqa/blob/main/docs/adr/{adr.name}"
        rows.append(f"| [{number}]({link}) | {title} | `{status}` |")

    parts = [
        render_frontmatter(
            title="Architecture Decision Records (ADRs)",
            description="Index of every accepted ADR in the SentinelQA codebase.",
            status=None,
        ),
        GENERATED_BANNER.format(generator="gen_adr_index", target="docs-gen-adr-index"),
        "",
        "An ADR records *why* a non-obvious architectural choice was made, "
        "so the next contributor can extend, supersede, or revisit it with "
        "context instead of re-deriving the trade-off from first principles.",
        "",
        "ADR source files live under `docs/adr/` in the repository. See "
        "[`docs/adr/README.md`]"
        "(https://github.com/Ohswedd/sentinelqa/blob/main/docs/adr/README.md)"
        " for the lifecycle rules and when an ADR is required "
        ".",
        "",
        "## Index",
        "",
        "\n".join(rows),
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    content = render()
    changed = write_if_changed(OUTPUT, content)
    sys.stdout.write(f"{'updated' if changed else 'unchanged'}: {OUTPUT.relative_to(REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
