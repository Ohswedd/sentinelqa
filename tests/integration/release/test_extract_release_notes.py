# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Release-notes extractor gate (Phase 36.05).

``scripts/release/extract_release_notes.py`` slices the relevant
``[tag]`` section out of ``CHANGELOG.md`` so the GitHub Release
workflow can feed it into ``softprops/action-gh-release``'s
``body_path`` parameter.

The tests cover:

* the live ``v1.0.0`` section of ``CHANGELOG.md`` extracts cleanly;
* tag normalisation (``v1.0.0`` and ``1.0.0`` are interchangeable);
* a missing tag exits non-zero;
* relative links are rewritten to absolute repo URLs;
* whitespace normalisation is deterministic;
* the heading line is dropped (GitHub renders its own ``<tag>`` title);
* the dedicated ``[Unreleased]`` and ``[0.7.0]`` sections also extract
  cleanly, so the extractor stays accurate for future tags;
* the workflow file uses the extractor and attaches the right files.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_extractor_is_importable_and_typed() -> None:
    from scripts.release import extract_release_notes

    assert callable(extract_release_notes.extract_section)
    assert callable(extract_release_notes.render_release_notes)
    assert callable(extract_release_notes.main)
    assert extract_release_notes.EXIT_OK == 0
    assert extract_release_notes.EXIT_FAIL == 2
    assert extract_release_notes.DEFAULT_REPO_URL.startswith("https://github.com/")


def test_live_v1_section_extracts() -> None:
    from scripts.release.extract_release_notes import render_release_notes

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = render_release_notes(changelog, "v1.0.0")
    assert body is not None
    # Heading line itself is dropped.
    assert not body.startswith("## ["), (
        "rendered release notes must not start with the `## [tag]` heading; " f"got: {body[:60]!r}"
    )
    # Body must mention every phase we shipped in v1.0.0.
    for phrase in (
        "phase-30",
        "phase-31",
        "phase-32",
        "phase-33",
        "phase-34",
        "phase-35",
        "phase-36",
    ):
        assert phrase in body, f"v1.0.0 release notes must mention {phrase}"
    # And it must stop before the next tag block (line-anchored — the
    # prose body legitimately mentions `## [0.7.0]` inside backticks).
    import re as _re

    assert not _re.search(
        r"^## \[0\.7\.0\]", body, flags=_re.MULTILINE
    ), "extractor must not bleed into the next tag's heading"


def test_live_v07_section_also_extracts() -> None:
    """The extractor must work for older tags too — release notes for a
    historical tag are sometimes regenerated."""

    from scripts.release.extract_release_notes import render_release_notes

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    body = render_release_notes(changelog, "v0.7.0")
    assert body is not None
    assert "phase-28" in body or "phase-29" in body
    import re as _re

    assert not _re.search(r"^## \[1\.0\.0\]", body, flags=_re.MULTILINE)
    assert not _re.search(r"^## \[0\.6\.0\]", body, flags=_re.MULTILINE)


def test_tag_normalisation_is_idempotent() -> None:
    from scripts.release.extract_release_notes import render_release_notes

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    with_v = render_release_notes(changelog, "v1.0.0")
    without_v = render_release_notes(changelog, "1.0.0")
    assert with_v == without_v
    assert with_v is not None


def test_missing_tag_returns_none() -> None:
    from scripts.release.extract_release_notes import render_release_notes

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert render_release_notes(changelog, "v99.99.99") is None


def test_missing_tag_exits_nonzero() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release.extract_release_notes",
            "v99.99.99",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "not found in" in proc.stderr


def test_relative_links_are_absolutised() -> None:
    from scripts.release.extract_release_notes import render_release_notes

    fake = textwrap.dedent(
        """
        # Changelog

        ## [1.0.0] - 2026-06-01

        See [the runbook](docs/release/publish-runbook.md) and
        [the upstream](https://example.com) and [the absolute](/docs/x.md)
        and [the anchor](#section).

        ## [0.9.0] - 2026-05-01

        Old stuff.
        """
    ).strip()

    body = render_release_notes(fake, "v1.0.0", repo_url="https://example.test/repo")
    assert body is not None
    # Relative link rewritten.
    assert (
        "[the runbook](https://example.test/repo/blob/main/docs/release/publish-runbook.md)" in body
    )
    # Absolute link untouched.
    assert "[the upstream](https://example.com)" in body
    # Repo-rooted absolute link untouched.
    assert "[the absolute](/docs/x.md)" in body
    # Anchor link untouched.
    assert "[the anchor](#section)" in body


def test_whitespace_normalisation_is_deterministic() -> None:
    from scripts.release.extract_release_notes import render_release_notes

    fake = "## [1.0.0] - 2026-06-01\n\n\n\nLine one.    \n\nLine two.\n\n\n\n"
    body = render_release_notes(fake, "v1.0.0")
    assert body is not None
    # No clusters of 3+ blank lines.
    assert "\n\n\n" not in body
    # No trailing whitespace per line.
    for line in body.splitlines():
        assert line == line.rstrip(), f"trailing whitespace on line: {line!r}"
    # Exactly one trailing newline.
    assert body.endswith("\n")
    assert not body.endswith("\n\n")


def test_output_is_byte_deterministic() -> None:
    """Running the extractor twice on the same input must produce
    byte-identical output."""

    from scripts.release.extract_release_notes import render_release_notes

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    a = render_release_notes(changelog, "v1.0.0")
    b = render_release_notes(changelog, "v1.0.0")
    assert a == b


def test_workflow_uses_extractor_and_attaches_artifacts() -> None:
    workflow = (REPO_ROOT / ".github/workflows/github-release.yml").read_text(encoding="utf-8")
    # The workflow runs the extractor.
    assert "scripts.release.extract_release_notes" in workflow
    # It uses softprops/action-gh-release.
    assert "softprops/action-gh-release@v2" in workflow
    # It feeds the extracted file in via body_path.
    assert "body_path: dist/release-notes.md" in workflow
    # It attaches every artifact category.
    for needle in ("dist/*.whl", "dist/*.tar.gz", "dist/sentinelqa-ts-runtime-*.tgz"):
        assert needle in workflow, f"workflow must attach {needle}"
    # It fails the workflow if any matcher returns no files.
    assert "fail_on_unmatched_files: true" in workflow


@pytest.mark.parametrize("tag", ["v1.0.0", "v0.7.0", "v0.1.0"])
def test_extractor_cli_smoke(tmp_path: Path, tag: str) -> None:
    """The CLI exits 0 and writes a file for every shipped tag."""

    out = tmp_path / f"{tag}.md"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release.extract_release_notes",
            tag,
            "-o",
            str(out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0
    assert out.is_file()
    assert out.stat().st_size > 0
