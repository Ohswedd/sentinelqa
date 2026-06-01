# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Extract a CHANGELOG.md section for a specific tag.

The GitHub Release workflow at ``.github/workflows/github-release.yml``
feeds this script's stdout into ``softprops/action-gh-release``'s
``body_path`` parameter so the release notes always come straight from
the curated CHANGELOG.

Usage::

 python -m scripts.release.extract_release_notes v1.0.0 \
 --changelog CHANGELOG.md \
 -o /tmp/release-notes.md

If the tag is not present in the changelog the script exits non-zero
with a clear error message — that is a release-blocking incident, not
a recoverable state.

The extractor also normalises Markdown for the GitHub Release page:

* Relative repository links (`docs/...`) become absolute URLs against
 the configured ``--repo-url``.
* The ``## [<tag>]`` heading is dropped (GitHub renders its own).
* Trailing whitespace and blank-line clusters are collapsed.

The output is deterministic — running the extractor twice on the same
inputs produces byte-identical Markdown.

Exit codes
----------

* ``0`` — section extracted, written to ``-o`` (or stdout).
* ``2`` — tag missing from the changelog, or output path unwritable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO_URL = "https://github.com/Ohswedd/sentinelqa"

EXIT_OK = 0
EXIT_FAIL = 2

_TAG_HEADING_RE = re.compile(r"^## \[(?P<tag>[^\]]+)\](?: - (?P<date>[^\n]+))?$", re.MULTILINE)


def _normalise_tag(tag: str) -> str:
    """Accept ``v1.0.0`` or ``1.0.0`` interchangeably."""

    return tag[1:] if tag.startswith("v") else tag


def extract_section(changelog: str, tag: str) -> str | None:
    """Return the body of the requested tag's section.

    The body excludes the ``## [tag]`` heading line itself and stops
    immediately before the next ``## [`` heading (or end of file).
    Returns ``None`` if the tag is absent.
    """

    needle = _normalise_tag(tag)
    matches = list(_TAG_HEADING_RE.finditer(changelog))
    for i, m in enumerate(matches):
        if m.group("tag") != needle:
            continue
        body_start = m.end() + 1  # skip the trailing newline of the heading
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog)
        return changelog[body_start:body_end]
    return None


def _absolutise_repo_links(body: str, repo_url: str) -> str:
    """Rewrite Markdown links to relative repo paths into absolute URLs.

    Pattern matched: ``[label](relative/path)`` where ``relative/path``
    does not look like a URL scheme (``http://``, ``https://``,
    ``mailto:``, ``#anchor``).

    The replacement points at the repo's ``main`` branch — that is
    what GitHub Releases display by default. For a tag-specific link
    the curator can hand-write the absolute URL in the changelog.
    """

    pattern = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)")

    def _rewrite(match: re.Match[str]) -> str:
        label = match.group("label")
        href = match.group("href").strip()
        if href.startswith(("http://", "https://", "mailto:", "#", "/")):
            return match.group(0)
        # Treat anything that looks like a relative path within the repo.
        if "/" in href or href.endswith((".md", ".py", ".ts", ".tsx", ".json", ".yaml", ".yml")):
            return f"[{label}]({repo_url}/blob/main/{href})"
        return match.group(0)

    return pattern.sub(_rewrite, body)


def _normalise_whitespace(body: str) -> str:
    body = re.sub(r"[ \t]+$", "", body, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


def render_release_notes(
    changelog: str, tag: str, *, repo_url: str = DEFAULT_REPO_URL
) -> str | None:
    body = extract_section(changelog, tag)
    if body is None:
        return None
    body = _absolutise_repo_links(body, repo_url)
    return _normalise_whitespace(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a tag's release notes from CHANGELOG.md for the GitHub Release."
    )
    parser.add_argument("tag", help="Tag to extract (e.g. v1.0.0 or 1.0.0).")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=REPO_ROOT / "CHANGELOG.md",
        help="Path to CHANGELOG.md (default: repo CHANGELOG.md).",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help=f"Repository URL used to absolutise relative links (default: {DEFAULT_REPO_URL}).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: stdout).",
    )
    args = parser.parse_args(argv)

    changelog_text = args.changelog.read_text(encoding="utf-8")
    body = render_release_notes(changelog_text, args.tag, repo_url=args.repo_url)
    if body is None:
        print(
            f"extract_release_notes: tag {args.tag!r} not found in {args.changelog}",
            file=sys.stderr,
        )
        return EXIT_FAIL

    if args.output is None:
        sys.stdout.write(body)
        return EXIT_OK

    args.output.write_text(body, encoding="utf-8")
    print(f"extract_release_notes: wrote {args.output} ({len(body)} bytes)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
