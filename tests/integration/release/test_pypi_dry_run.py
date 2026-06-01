# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""PyPI dry-run gate (Phase 36.02).

``scripts/release/dry_run_pypi.py`` must exit 0 on the current
``main`` so the owner can run it locally before pushing the
``v*`` tag and know the artifacts will pass PyPI's strict metadata
gate. The CI run validates this on every PR / push to
``feature/phase-36-*`` and ``main``.

The actual upload is owner-only and never happens in this test —
the script is hard-coded to ``twine check``, never ``twine upload``.

The full build is slow (uv build + twine check across 12 artifacts),
so the headline test is marked ``@pytest.mark.slow``. A lighter
non-slow test asserts the script's module structure so the slow
test stays the only one that pays the build cost.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def test_dry_run_script_is_importable_and_typed() -> None:
    """Light gate: the script exposes the documented API.

    Keeps the slow build out of every PR while still failing fast if
    the script regresses to a non-functional state.
    """

    from scripts.release import dry_run_pypi

    assert callable(dry_run_pypi.run_dry_run)
    assert callable(dry_run_pypi.main)
    # Documented exit codes are stable contract.
    assert dry_run_pypi.EXIT_OK == 0
    assert dry_run_pypi.EXIT_FAIL == 2
    assert dry_run_pypi.EXIT_DEP_MISSING == 5


def test_dry_run_script_never_calls_twine_upload() -> None:
    """The script may NEVER invoke ``twine upload`` — that is owner-only
    (our engineering rules + §40 + docs/release/publish-runbook.md)."""

    source = (REPO_ROOT / "scripts/release/dry_run_pypi.py").read_text(encoding="utf-8")
    forbidden = ("twine upload", "twine_upload", "pypi-upload", '"upload"', "'upload'")
    for needle in forbidden:
        assert needle not in source, (
            f"scripts/release/dry_run_pypi.py must not reference {needle!r} — "
            "the dry-run is `twine check` only"
        )


def test_publish_workflow_never_skips_existing() -> None:
    """A tag push must not silently no-op against a name collision.

    ``pypa/gh-action-pypi-publish`` accepts ``skip-existing: true`` which
    is a footgun: a re-pushed tag will quietly succeed even though
    nothing was published. The publish runbook treats a name collision
    as an incident, not a recoverable state — so the workflow pins
    ``skip-existing: false`` and we lock that here.
    """

    workflow = (REPO_ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
    assert "skip-existing: false" in workflow, "publish-pypi.yml must pin `skip-existing: false`"


def test_publish_workflow_uses_trusted_publisher_oidc() -> None:
    workflow = (REPO_ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
    # OIDC token write permission (the trusted-publisher contract).
    assert "id-token: write" in workflow
    # No long-lived API token in env: the publish step must not name
    # PYPI_API_TOKEN or TWINE_PASSWORD.
    for forbidden in ("PYPI_API_TOKEN", "TWINE_PASSWORD", "TWINE_USERNAME"):
        assert (
            forbidden not in workflow
        ), f"publish-pypi.yml must not reference {forbidden} — trusted-publisher only"
    # The environment gate (manual approval) is wired.
    assert "environment:" in workflow
    assert "name: pypi-release" in workflow


def test_publish_workflow_verifies_installed_version_matches_tag() -> None:
    workflow = (REPO_ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
    # The verify job must install the just-published package and check
    # ``sentinel --version`` actually reports the tag's version.
    assert "verify (install from PyPI)" in workflow
    assert "sentinelqa-cli==${VERSION}" in workflow
    assert "sentinel --version" in workflow


@pytest.mark.slow
@pytest.mark.skipif(not _have("uv"), reason="uv not on PATH")
def test_dry_run_pypi_succeeds_on_current_main(tmp_path: Path) -> None:
    """Full build + twine check --strict on the live tree.

    Slow tier — runs on ``make test-full`` and on the publish-pypi
    workflow's `build` job.
    """

    dist = tmp_path / "dist"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release.dry_run_pypi",
            "--out-dir",
            str(dist),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0, "dry_run_pypi must exit 0 on current main"
    # And the success line must have landed in stdout.
    assert "dry_run_pypi: ok" in proc.stdout
