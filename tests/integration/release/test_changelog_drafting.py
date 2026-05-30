"""Regression tests for ``scripts/release/draft_changelog.py``.

The drafter is pure-stdlib, so we exercise both the parser (unit-level, with
synthetic ``git log`` lines) and the CLI (subprocess-level, against the live
repo) to prove ``make changelog-draft`` will keep producing sensible output as
new phases land.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release" / "draft_changelog.py"


# Make scripts.release importable without installing it as a package.
def _ensure_scripts_on_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _path() -> None:
    _ensure_scripts_on_path()


# --------------------------------------------------------------------------- #
# Parser unit tests (no subprocess)
# --------------------------------------------------------------------------- #


def test_script_file_exists() -> None:
    assert SCRIPT_PATH.is_file(), f"drafter missing: {SCRIPT_PATH}"


def test_parse_feat_maps_to_added() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "feat(planner): add deterministic planner")
    assert c is not None
    assert c.type == "feat"
    assert c.scope == "planner"
    assert c.summary == "add deterministic planner"
    assert c.category == "Added"
    assert c.breaking is False


def test_parse_fix_maps_to_fixed() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "fix(runner): handle partial stream tail")
    assert c is not None
    assert c.category == "Fixed"


def test_parse_security_maps_to_security() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "security(repo): adopt apache-2.0 license")
    assert c is not None
    assert c.category == "Security"


def test_parse_refactor_and_perf_map_to_changed() -> None:
    from scripts.release.draft_changelog import parse_subject

    a = parse_subject("a", "refactor(scoring): split severity ladder")
    b = parse_subject("b", "perf(reporter): cache trend serialisation")
    assert a is not None and a.category == "Changed"
    assert b is not None and b.category == "Changed"


def test_parse_internal_types_grouped_under_internal() -> None:
    from scripts.release.draft_changelog import parse_subject

    for ctype in ("chore", "ci", "build", "test", "docs", "style"):
        c = parse_subject("abc1234", f"{ctype}(scope): summary text")
        assert c is not None, f"failed to parse {ctype}"
        assert c.category == "Internal"


def test_parse_breaking_change_maps_to_changed() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "feat(cli)!: drop deprecated --legacy-flag")
    assert c is not None
    assert c.breaking is True
    assert c.category == "Changed"


def test_parse_phase_legacy_subject_maps_to_added() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "Phase 04: TypeScript Playwright runtime (#4)")
    assert c is not None
    assert c.type == "feat"
    assert c.scope == "phase-04"
    assert c.summary.startswith("TypeScript Playwright runtime")
    assert c.category == "Added"


def test_parse_lowercase_phase_subject_maps_to_added() -> None:
    from scripts.release.draft_changelog import parse_subject

    c = parse_subject("abc1234", "phase 21: visual-regression module — pillow diff")
    assert c is not None
    assert c.scope == "phase-21"
    assert c.category == "Added"


def test_parse_unknown_returns_none() -> None:
    from scripts.release.draft_changelog import parse_subject

    assert parse_subject("abc1234", "wip: prototype") is None
    assert parse_subject("abc1234", "random subject without a type") is None


def test_parse_log_filters_out_unrecognised_and_blanks() -> None:
    from scripts.release.draft_changelog import parse_log

    lines = [
        "aaa1\tfeat(cli): land sentinel test",
        "",
        "bbb2\twip: throwaway",
        "ccc3\tfix(runner): handle partial stream",
        "ddd4\tnotabhash without tab",
    ]
    commits = parse_log(lines)
    assert [c.sha for c in commits] == ["aaa1", "ccc3"]
    assert [c.category for c in commits] == ["Added", "Fixed"]


# --------------------------------------------------------------------------- #
# Grouping + rendering
# --------------------------------------------------------------------------- #


def test_group_commits_preserves_kac_order() -> None:
    from scripts.release.draft_changelog import (
        CHANGELOG_ORDER,
        group_commits,
        parse_log,
    )

    lines = [
        "sec1\tsecurity(repo): redact webhook url",
        "fix1\tfix(runner): swallow partial stream",
        "feat1\tfeat(cli): land sentinel test",
        "ref1\trefactor(scoring): split severity ladder",
    ]
    groups = group_commits(parse_log(lines), include_internal=False)
    keys = list(groups.keys())
    assert keys == list(CHANGELOG_ORDER), keys
    assert [c.sha for c in groups["Added"]] == ["feat1"]
    assert [c.sha for c in groups["Changed"]] == ["ref1"]
    assert [c.sha for c in groups["Fixed"]] == ["fix1"]
    assert [c.sha for c in groups["Security"]] == ["sec1"]


def test_render_section_omits_empty_buckets() -> None:
    from scripts.release.draft_changelog import (
        group_commits,
        parse_log,
        render_section,
    )

    lines = ["feat1\tfeat(cli): land sentinel test"]
    groups = group_commits(parse_log(lines), include_internal=False)
    out = render_section(groups, version="0.1.0", date="2026-05-29")
    assert "## [0.1.0] - 2026-05-29" in out
    assert "### Added" in out
    assert "### Changed" not in out
    assert "### Fixed" not in out
    assert "land sentinel test" in out
    assert "(feat1)" in out


def test_render_section_renders_empty_range_marker() -> None:
    from scripts.release.draft_changelog import render_section

    out = render_section(
        {k: [] for k in ("Added", "Changed", "Fixed")},
        version="Unreleased",
        date="",
    )
    assert "## [Unreleased]" in out
    assert "_No user-visible changes in this range._" in out


def test_internal_bucket_included_when_requested() -> None:
    from scripts.release.draft_changelog import (
        INTERNAL_CATEGORY,
        group_commits,
        parse_log,
    )

    lines = ["chore1\tchore(tooling): bump pytest"]
    g_off = group_commits(parse_log(lines), include_internal=False)
    g_on = group_commits(parse_log(lines), include_internal=True)
    assert INTERNAL_CATEGORY not in g_off
    assert INTERNAL_CATEGORY in g_on
    assert [c.sha for c in g_on[INTERNAL_CATEGORY]] == ["chore1"]


def test_render_entry_marks_breaking() -> None:
    from scripts.release.draft_changelog import parse_subject, render_entry

    c = parse_subject("abc1234", "feat(cli)!: drop --legacy-flag")
    assert c is not None
    entry = render_entry(c)
    assert "**BREAKING**" in entry
    assert "**cli**" in entry
    assert "(abc1234)" in entry


# --------------------------------------------------------------------------- #
# CLI smoke test — against a hermetic tmp git repo so CI shallow clones don't
# trip up the test (the live repo's --max-parents=0 root is unreachable under
# `actions/checkout`'s default fetch-depth=1).
# --------------------------------------------------------------------------- #


def _run_drafter(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
        check=False,
    )


def _git(cwd: Path, *args: str) -> None:
    import os as _os

    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={
            **_os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


def _init_synth_repo(root: Path, *subjects: str) -> None:
    """Initialise a synthetic git repo with one commit per subject (no merges)."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    for i, subject in enumerate(subjects):
        (root / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", subject)


def test_drafter_against_synthetic_repo_produces_unreleased_section(tmp_path: Path) -> None:
    repo = tmp_path / "synth"
    _init_synth_repo(
        repo,
        "feat(cli): land sentinel test",
        "fix(runner): handle partial stream",
        "security(repo): redact webhook url",
        "phase 02: cli skeleton, run lifecycle, artifact tree",
        "chore(tooling): bump pytest",
    )

    result = _run_drafter("--to", "HEAD", "--version", "X.Y.Z", cwd=repo)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "## [X.Y.Z]" in out
    # feat + phase both go under Added; fix → Fixed; security → Security.
    assert "### Added" in out
    assert "land sentinel test" in out
    assert "**phase-02**" in out
    assert "### Fixed" in out
    assert "### Security" in out
    # chore is internal and excluded by default.
    assert "### Internal" not in out


def test_drafter_writes_output_file(tmp_path: Path) -> None:
    repo = tmp_path / "synth"
    _init_synth_repo(repo, "feat(cli): land sentinel test")

    out_file = tmp_path / "draft.md"
    result = _run_drafter("--to", "HEAD", "-o", str(out_file), cwd=repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""  # quiet when -o is used
    text = out_file.read_text(encoding="utf-8")
    assert "## [Unreleased]" in text
    assert "### Added" in text
    assert "land sentinel test" in text


def test_drafter_includes_internal_when_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "synth"
    _init_synth_repo(
        repo,
        "feat(cli): land sentinel test",
        "chore(tooling): bump pytest",
    )

    result = _run_drafter("--to", "HEAD", "--include-internal", "--version", "0.1.0", cwd=repo)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "### Added" in out
    assert "### Internal" in out
    assert "bump pytest" in out


def test_canonical_changelog_file_exists_and_references_keep_a_changelog() -> None:
    path = REPO_ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    assert "Keep a Changelog" in text
    assert "Semantic Versioning" in text
    # Every released version section MUST appear.
    for section in (
        "## [Unreleased]",
        "## [0.6.0]",
        "## [0.5.0]",
        "## [0.4.0]",
        "## [0.3.0]",
        "## [0.2.0]",
        "## [0.1.0]",
    ):
        assert section in text, f"missing section: {section}"


def test_cliff_toml_exists_and_targets_the_same_categories() -> None:
    path = REPO_ROOT / "cliff.toml"
    text = path.read_text(encoding="utf-8")
    # Parity with the Python drafter's category mapping.
    for line in (
        '{ message = "^feat", group = "Added" }',
        '{ message = "^fix", group = "Fixed" }',
        '{ message = "^security", group = "Security" }',
        '{ message = "^refactor", group = "Changed" }',
        '{ message = "^perf", group = "Changed" }',
    ):
        assert line in text, f"missing parser entry: {line}"


def test_release_template_exists() -> None:
    path = REPO_ROOT / ".github" / "changelog-template.md"
    text = path.read_text(encoding="utf-8")
    assert "SentinelQA vX.Y.Z" in text
    assert "Breaking changes" in text
    assert "docs/dev/semver.md" in text
