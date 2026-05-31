# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""v1.0.0 tag-prep gate (Phase 36.01).

The first publication-eligible tag is ``v1.0.0`` per
``docs/dev/semver.md``. This file enforces, at every CI run on the
phase-36 branch and on ``main`` afterwards, that:

* every publishable Python pyproject and the npm ts-runtime manifest
  read the canonical ``v1.0.0`` version;
* the Python SDK API snapshot is fresh;
* ``CHANGELOG.md`` has a curated ``[1.0.0]`` section in the
  canonical position (top of the version list, after
  ``[Unreleased]``);
* ``docs/dev/semver.md`` carries a ``v1.0.0`` row that points at
  Phase 36;
* ``docs/release/pre-1.0-review.md`` has a fresh ``v1.0.0`` draft
  sign-off block with every numeric gate pre-filled;
* the ts-runtime manifest is publication-ready: ``private:true``
  removed, ``files:`` whitelist tightened to dist + LICENSE + README,
  exports point at the compiled ``dist/`` tree, and
  ``publishConfig`` opts every consumer into the public registry
  with provenance.

The `make build-all` artifact-count gate (the "13 artifacts at
1.0.0" line) is exercised separately by
``tests/integration/release/test_built_packages.py`` so this file
does not need to spawn a build subprocess.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_VERSION = "1.0.0"

PUBLISHABLE_PY: tuple[str, ...] = (
    "apps/cli/pyproject.toml",
    "engine/pyproject.toml",
    "modules/pyproject.toml",
    "integrations/pyproject.toml",
    "packages/python-sdk/pyproject.toml",
    "packages/mcp-server/pyproject.toml",
)

PUBLISHABLE_TS: str = "packages/ts-runtime/package.json"


def _load_toml(rel: str) -> dict:
    with (REPO_ROOT / rel).open("rb") as fh:
        return tomllib.load(fh)


def _load_json(rel: str) -> dict:
    data = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.parametrize("rel", PUBLISHABLE_PY)
def test_python_manifests_read_v1(rel: str) -> None:
    data = _load_toml(rel)
    assert data["project"]["version"] == EXPECTED_VERSION, (
        f"{rel} must declare project.version = {EXPECTED_VERSION!r}; "
        f"got {data['project']['version']!r}"
    )


def test_ts_runtime_manifest_reads_v1() -> None:
    data = _load_json(PUBLISHABLE_TS)
    assert data["version"] == EXPECTED_VERSION


def test_ts_runtime_manifest_is_publication_ready() -> None:
    """Phase 36.01 + 36.03 publication-surface invariants.

    These all live on the same file so they collapse into one test
    rather than a noisy six-test parametrisation.
    """

    data = _load_json(PUBLISHABLE_TS)

    # 1. `private:true` removed for the public publish.
    assert "private" not in data, (
        "packages/ts-runtime/package.json must NOT declare `private: true` at v1.0.0 "
        "(Phase 36.03 — public npm publish)"
    )

    # 2. `files:` whitelist ships dist + docs only.
    files = data.get("files")
    assert isinstance(files, list) and files, "files: must be a non-empty allowlist"
    must_include = {"dist/**", "README.md", "LICENSE"}
    have = set(files)
    missing = must_include - have
    assert not missing, f"files: missing required entries: {sorted(missing)}"
    # No src/ shipped — sources stay in the workspace.
    assert not any(
        entry.startswith("src/") for entry in files
    ), "files: must not ship src/ once v1.0.0 publishes from dist/"

    # 3. exports point at dist/.
    exports = data.get("exports")
    assert isinstance(exports, dict)
    for subpath, mapping in exports.items():
        assert isinstance(mapping, dict), f"exports[{subpath!r}] must be a conditional mapping"
        for cond, target in mapping.items():
            assert target.startswith(
                "./dist/"
            ), f"exports[{subpath!r}][{cond!r}] must point at ./dist/, got {target!r}"

    # 4. main/types point at dist/.
    assert data.get("main", "").startswith("./dist/")
    assert data.get("types", "").startswith("./dist/")

    # 5. publishConfig opts every consumer into public + provenance.
    publish_config = data.get("publishConfig")
    assert isinstance(
        publish_config, dict
    ), "packages/ts-runtime/package.json must declare publishConfig for v1.0.0"
    assert publish_config.get("access") == "public"
    assert publish_config.get("provenance") is True


def test_python_sdk_api_snapshot_is_fresh() -> None:
    """The snapshot must equal what ``scripts/dump-sdk-api-snapshot.py`` emits today.

    The Phase 16 unit test ``tests/unit/sdk/test_api_snapshot.py`` already
    diffs the live surface against the snapshot, so this test only
    verifies the snapshot file is present and parseable (a regression
    against the snapshot itself would fail that unit test).
    """

    snapshot = REPO_ROOT / "packages/python-sdk/api-snapshot.json"
    assert snapshot.is_file(), "packages/python-sdk/api-snapshot.json must be present"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "api-snapshot.json must be a JSON object"
    # The snapshot is keyed by symbol path; require at least one entry so an
    # empty/truncated file fails this gate.
    assert data, "api-snapshot.json must be non-empty"


def test_changelog_has_curated_v1_section() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    # The [1.0.0] header must be present with a real ISO date.
    assert re.search(
        r"^## \[1\.0\.0\] - \d{4}-\d{2}-\d{2}$",
        text,
        flags=re.MULTILINE,
    ), "CHANGELOG.md must carry a curated `## [1.0.0] - YYYY-MM-DD` section"

    # And it must come BEFORE [0.7.0] in the file (canonical Keep a
    # Changelog ordering: newest at top).
    v1_pos = text.index("## [1.0.0] - ")
    v07_pos = text.index("## [0.7.0] - ")
    assert v1_pos < v07_pos, "CHANGELOG.md must list [1.0.0] above [0.7.0] (newest first)"

    # The duplicated `## [0.7.0]` header artefact must be gone (Phase
    # 28 paste residue cleaned up in Phase 36). Only count occurrences
    # that are real Markdown headings — start of line.
    heading_count = len(re.findall(r"^## \[0\.7\.0\] - 2026-05-31$", text, flags=re.MULTILINE))
    assert heading_count == 1, (
        "CHANGELOG.md must contain exactly one `## [0.7.0] - 2026-05-31` heading; "
        f"found {heading_count}"
    )


def test_semver_tag_plan_has_phase36_v1_row() -> None:
    semver = (REPO_ROOT / "docs/dev/semver.md").read_text(encoding="utf-8")
    # Find the v1.0.0 row of the tag-plan table.
    row_pattern = re.compile(r"^\| `v1\.0\.0` \| (.*?) \| (.*?) \|$", re.MULTILINE)
    match = row_pattern.search(semver)
    assert match is not None, "docs/dev/semver.md must contain a `v1.0.0` tag-plan row"
    when, captures = match.group(1), match.group(2)
    assert "Phase 36" in when, (
        f"docs/dev/semver.md `v1.0.0` row must reference Phase 36 in the 'When' "
        f"column; got {when!r}"
    )
    # Captures column must mention the phase span and the version bump.
    for needle in ("Phase 30", "Phase 36", "ADR-0048", EXPECTED_VERSION):
        assert needle in captures, (
            f"docs/dev/semver.md `v1.0.0` row 'Captures' column must mention {needle!r}; "
            f"got {captures!r}"
        )


def test_pre1_review_has_v1_draft_signoff() -> None:
    review = (REPO_ROOT / "docs/release/pre-1.0-review.md").read_text(encoding="utf-8")
    # Heading.
    assert (
        "### Draft sign-off — v1.0.0" in review
    ), "pre-1.0-review.md must carry a `### Draft sign-off — v1.0.0` section"

    # Pull the v1 block (from its heading to the next heading) and check the
    # numeric gates are pre-filled.
    v1_start = review.index("### Draft sign-off — v1.0.0")
    next_heading = review.index("\n### ", v1_start + 1)
    block = review[v1_start:next_heading]

    for needle in (
        "## Tag: v1.0.0",
        "Branch:         feature/phase-36-publish-ecosystem",
        "make audit-metadata: ok",
        "make build-all: ",
        "make inspect-all: ok",
        "13 artifacts total",
        "sentinelqa-ts-runtime-1.0.0.tgz",
    ):
        assert needle in block, f"pre-1.0-review.md v1.0.0 sign-off block must contain {needle!r}"


def test_unreleased_section_is_clean() -> None:
    """After the v1 cut, ``[Unreleased]`` should not still carry the
    Phase 30..36 planning bullets (they have shipped)."""

    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased_start = text.index("## [Unreleased]")
    next_heading = text.index("\n## [", unreleased_start + 1)
    block = text[unreleased_start:next_heading]
    forbidden_phrases = (
        "plans/phase-30-",
        "plans/phase-31-",
        "plans/phase-32-",
        "plans/phase-33-",
        "plans/phase-34-",
        "plans/phase-35-",
        "plans/phase-36-",
    )
    for phrase in forbidden_phrases:
        assert (
            phrase not in block
        ), f"CHANGELOG.md `[Unreleased]` section still references {phrase!r} after the v1 cut"
