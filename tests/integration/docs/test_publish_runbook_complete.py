# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Publish-runbook completeness gate (Phase 36.07).

``docs/release/publish-runbook.md`` is the owner-facing single
source of truth for cutting a real publish. This test enforces
that future edits cannot:

* drop the warning header that names the agent boundary;
* leave a workflow file referenced without it existing on disk;
* leave a dry-run script referenced without it existing on disk;
* drop the closing line that warns the human to read twice.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs/release/publish-runbook.md"


def _text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_runbook_exists() -> None:
    assert RUNBOOK.is_file(), "docs/release/publish-runbook.md must exist (Phase 36.07)"


def test_runbook_has_agent_boundary_warning_header() -> None:
    text = _text()
    # The exact phrasing of the warning is locked so a future polish
    # can't trim it down to "for the owner" without losing the
    # CLAUDE.md §3 + §40 citation.
    must_include = (
        "This page is for the human owner",
        "will not run any `twine upload` / `pnpm publish` / `docker push` / `git tag`",
        "every command in this file is",
        "something the owner runs themselves",
        "CLAUDE.md` §3 + §40",
    )
    for needle in must_include:
        assert (
            needle in text
        ), f"docs/release/publish-runbook.md warning header must contain {needle!r}"


def test_runbook_has_closing_warning() -> None:
    text = _text()
    closing = (
        "# This is the only time SentinelQA actually publishes to the public registries. "
        "Read it twice before running."
    )
    assert closing in text, "runbook must end with the canonical closing warning line"


def test_runbook_references_every_publish_workflow() -> None:
    text = _text()
    for workflow in (
        "publish-pypi.yml",
        "publish-npm.yml",
        "publish-docker.yml",
        "github-release.yml",
    ):
        assert workflow in text, f"runbook must reference {workflow}"
        assert (
            REPO_ROOT / ".github/workflows" / workflow
        ).is_file(), f".github/workflows/{workflow} must exist on disk"


def test_runbook_references_every_dry_run_script() -> None:
    text = _text()
    scripts = (
        "scripts.release.dry_run_pypi",
        "scripts.release.dry_run_npm",
        "scripts.release.dry_run_docker",
        "scripts.release.extract_release_notes",
    )
    for module in scripts:
        assert module in text, f"runbook must reference {module}"
        # Module-path -> file-path.
        path = REPO_ROOT / (module.replace(".", "/") + ".py")
        assert path.is_file(), f"{path} must exist on disk"


def test_runbook_references_post_publish_smoke() -> None:
    text = _text()
    assert "SENTINELQA_TEST_POST_PUBLISH=1" in text
    assert "tests/integration/release/test_post_publish_smoke.py" in text


def test_runbook_references_pre1_review_signoff() -> None:
    text = _text()
    assert "docs/release/pre-1.0-review.md" in text


def test_runbook_names_every_environment() -> None:
    text = _text()
    for env in (
        "pypi-release",
        "npm-release",
        "docker-release",
        "github-release",
    ):
        assert env in text, f"runbook must name the `{env}` GitHub Environment"


def test_runbook_forbids_agent_publish_actions() -> None:
    """The runbook must explicitly enumerate the operations the agent
    will NOT perform, so a future contributor cannot quietly relax
    the boundary."""

    text = _text()
    must_forbid = (
        "agent**",
        "never runs",
        "git tag",
        "twine upload",
        "pnpm publish",
        "docker push",
    )
    for needle in must_forbid:
        assert needle in text, f"runbook must explicitly state the agent does not run {needle!r}"
