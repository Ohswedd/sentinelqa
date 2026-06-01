"""Status-label CI guard.

Every feature page under ``apps/docs/src/content/docs/`` must declare a
``status:`` frontmatter field of one of
``Stable | Experimental | Planned | Deprecated`` (docs/dev/status-labels.md).

Exemptions are intentional:
 * the docs landing page (`index.md`) is a hero / splash page;
 * the ADR index is auto-generated and represents documents whose status
 lives on the linked ADR, not on the index itself.

Both exemptions are encoded below as exact paths so missing labels remain
loud.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT_ROOT = REPO_ROOT / "apps" / "docs" / "src" / "content" / "docs"

ALLOWED = {"Stable", "Experimental", "Planned", "Deprecated"}

EXEMPT_PATHS = {
    CONTENT_ROOT / "index.md",
    CONTENT_ROOT / "adrs" / "index.md",
}

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)


def _iter_feature_pages() -> list[Path]:
    return sorted(p for p in CONTENT_ROOT.rglob("*.md") if p not in EXEMPT_PATHS)


def test_every_feature_page_has_a_status_label() -> None:
    missing: list[str] = []
    invalid: list[str] = []

    for page in _iter_feature_pages():
        text = page.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            missing.append(str(page.relative_to(REPO_ROOT)))
            continue
        frontmatter = match.group(1)
        status_match = STATUS_RE.search(frontmatter)
        if not status_match:
            missing.append(str(page.relative_to(REPO_ROOT)))
            continue
        value = status_match.group(1)
        if value not in ALLOWED:
            invalid.append(f"{page.relative_to(REPO_ROOT)}: status={value!r}")

    assert not missing, (
        "Missing `status:` frontmatter on these feature pages "
        "(allowed: Stable | Experimental | Planned | Deprecated):\n"
        + "\n".join(f"  - {m}" for m in missing)
    )
    assert not invalid, (
        "Invalid `status:` value on these feature pages "
        "(allowed: Stable | Experimental | Planned | Deprecated):\n"
        + "\n".join(f"  - {v}" for v in invalid)
    )


def test_exempt_paths_exist() -> None:
    # Guard against silent drift: if a path is removed from the exempt list
    # but no longer exists, the previous test would silently pass instead of
    # flagging the missing exemption.
    for path in EXEMPT_PATHS:
        assert path.exists(), f"exempt path missing: {path.relative_to(REPO_ROOT)}"
