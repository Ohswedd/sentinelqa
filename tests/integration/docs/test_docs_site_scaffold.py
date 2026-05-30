"""Structural checks for the Phase 27 docs site (apps/docs/).

Asserts the scaffold's invariants without running Astro:
  * the package is registered as `@sentinelqa/docs`
  * sidebar entries in `astro.config.mjs` correspond to files on disk
  * the docs site lives in the pnpm workspace
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO_ROOT / "apps" / "docs"
CONTENT_ROOT = DOCS_ROOT / "src" / "content" / "docs"
ASTRO_CONFIG = DOCS_ROOT / "astro.config.mjs"
PACKAGE_JSON = DOCS_ROOT / "package.json"
PNPM_WORKSPACE = REPO_ROOT / "pnpm-workspace.yaml"

SIDEBAR_LINK_RE = re.compile(r'link:\s*["\']([^"\']+)["\']')


def test_package_metadata() -> None:
    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert pkg["name"] == "@sentinelqa/docs"
    assert pkg["private"] is True
    assert "build" in pkg["scripts"]
    assert "astro" in pkg["dependencies"]
    assert "@astrojs/starlight" in pkg["dependencies"]


def test_pnpm_workspace_includes_docs() -> None:
    text = PNPM_WORKSPACE.read_text(encoding="utf-8")
    assert "apps/docs" in text, "apps/docs is not in pnpm-workspace.yaml"


@pytest.fixture(scope="module")
def sidebar_links() -> list[str]:
    raw = ASTRO_CONFIG.read_text(encoding="utf-8")
    return SIDEBAR_LINK_RE.findall(raw)


def test_sidebar_links_resolve_to_existing_pages(sidebar_links: list[str]) -> None:
    missing: list[str] = []
    for link in sidebar_links:
        # External links pass through unchanged
        if link.startswith("http"):
            continue
        # Strip leading and trailing slashes; Starlight maps `/foo/bar/`
        # onto `src/content/docs/foo/bar.md` or `.../bar/index.md`.
        slug = link.strip("/")
        if not slug:
            candidate = CONTENT_ROOT / "index.md"
        else:
            candidate_md = CONTENT_ROOT / f"{slug}.md"
            candidate_index = CONTENT_ROOT / slug / "index.md"
            candidate = candidate_md if candidate_md.exists() else candidate_index
        if not candidate.exists():
            missing.append(f"{link} → {candidate.relative_to(REPO_ROOT)}")

    assert not missing, "Sidebar links point at non-existent pages:\n" + "\n".join(
        f"  - {m}" for m in missing
    )


def test_every_module_page_starts_with_status() -> None:
    module_pages = sorted((CONTENT_ROOT / "modules").glob("*.md"))
    assert module_pages, "no module pages under apps/docs/src/content/docs/modules/"
    for page in module_pages:
        if page.name == "index.md":
            continue
        text = page.read_text(encoding="utf-8")
        assert "status: Stable" in text, f"{page.name}: shipped modules should declare Stable"
