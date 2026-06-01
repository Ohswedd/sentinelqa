# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""README link health.

Asserts the public-facing `README.md` (Phase 35.01) keeps its claims
testable: every relative link resolves on disk, every external URL is
well-formed (no `http`-only links unless explicitly whitelisted), the
file stays under the line cap, the safety boundary is preserved, and
no buzzwords leak in.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "README.md"

# Lines cap from the build plan
MAX_LINES = 250

# Buzzwords forbidden by the same task ("no marketing fluff").
FORBIDDEN_TERMS = ("AI-powered", "magic", "intelligent")

# Markdown link extraction. We accept inline links [text](url) and
# image links ![alt](url). Reference-style links are intentionally
# disallowed for the README (one place to read, no indirection).
LINK_RE = re.compile(r"!?\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# External URLs we accept even before the public flip / DNS lands.
# Each entry must be justified by a comment.
ALLOWED_EXTERNAL_HOSTS = {
    # Repository home — owner-controlled.
    "github.com",
    # Badge CDN — read-only, owner-agnostic.
    "img.shields.io",
    # Docs site — DNS provisioned by owner in task 35.04; the link is
    # ratified here even before the CNAME resolves so the README does
    # not need a follow-up edit on the day the site flips.
    "docs.sentinelqa.dev",
}


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_exists() -> None:
    assert README.is_file(), "README.md missing at repo root"


def test_readme_under_line_cap() -> None:
    lines = _readme_text().splitlines()
    assert (
        len(lines) <= MAX_LINES
    ), f"README.md is {len(lines)} lines; task 35.01 caps it at {MAX_LINES}."


def test_no_marketing_buzzwords() -> None:
    text = _readme_text()
    hits = [t for t in FORBIDDEN_TERMS if t.lower() in text.lower()]
    assert not hits, (
        "README.md contains forbidden marketing terms (task 35.01 — "
        f"'no AI-powered / magic / intelligent buzzwords'): {hits}"
    )


def test_safety_boundary_present() -> None:
    text = _readme_text()
    assert (
        "Safety boundary" in text
    ), "README.md must surface the our engineering rules safety boundary."
    assert (
        "authorized testing only" in text.lower()
    ), "README.md must state SentinelQA is for authorized testing only."


def test_quickstart_block_present() -> None:
    text = _readme_text()
    for command in (
        "uv pip install sentinelqa-cli",
        "sentinel init",
        "sentinel audit --url http://localhost:3000",
    ):
        assert command in text, f"README.md quickstart must show `{command}` verbatim (task 35.01)."


def _iter_links() -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in LINK_RE.finditer(_readme_text())]


def test_relative_links_resolve_on_disk() -> None:
    failures: list[str] = []
    for text, url in _iter_links():
        parsed = urlparse(url)
        if parsed.scheme:
            continue
        if url.startswith("#"):
            continue
        # Strip anchor + query; we only verify the path component.
        path_only = url.split("#", 1)[0].split("?", 1)[0]
        # Leading ./ is fine; normalize.
        rel = path_only[2:] if path_only.startswith("./") else path_only
        candidate = (REPO_ROOT / rel).resolve()
        if not candidate.exists():
            failures.append(f"[{text}]({url}) → missing path {candidate}")
    assert not failures, "Broken relative links in README.md:\n" + "\n".join(failures)


def test_external_links_well_formed_and_allowlisted() -> None:
    failures: list[str] = []
    for text, url in _iter_links():
        parsed = urlparse(url)
        if not parsed.scheme:
            continue
        if parsed.scheme not in {"http", "https"}:
            failures.append(f"[{text}]({url}) → unsupported scheme {parsed.scheme!r}")
            continue
        if not parsed.netloc:
            failures.append(f"[{text}]({url}) → missing netloc")
            continue
        if parsed.netloc not in ALLOWED_EXTERNAL_HOSTS:
            failures.append(
                f"[{text}]({url}) → host {parsed.netloc!r} not on the "
                "README allowlist; add a justified entry to "
                "ALLOWED_EXTERNAL_HOSTS in this test if intentional."
            )
    assert not failures, "External-link issues in README.md:\n" + "\n".join(failures)


def test_demo_asset_referenced_and_present() -> None:
    text = _readme_text()
    asset = REPO_ROOT / "docs" / "assets" / "demo-audit.svg"
    assert asset.is_file(), f"Demo asset missing at {asset}"
    assert "docs/assets/demo-audit.svg" in text, "README.md must embed the demo asset (task 35.01)."
