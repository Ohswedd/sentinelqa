# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""npm dry-run gate (Phase 36.03).

``scripts/release/dry_run_npm.py`` must exit 0 on the current
``main`` so the owner can validate the @sentinelqa/ts-runtime
tarball locally before pushing the ``v*`` tag.

The actual publish is owner-only and never happens in this test —
the script is hard-coded to ``pnpm pack`` + ``npm publish --dry-run``,
never ``pnpm publish`` / ``npm publish`` (no ``--dry-run``).
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
    from scripts.release import dry_run_npm

    assert callable(dry_run_npm.run_dry_run)
    assert callable(dry_run_npm.main)
    assert callable(dry_run_npm.inspect_tarball)
    # Documented exit codes are stable contract.
    assert dry_run_npm.EXIT_OK == 0
    assert dry_run_npm.EXIT_FAIL == 2
    assert dry_run_npm.EXIT_DEP_MISSING == 5


def test_dry_run_script_never_calls_real_publish() -> None:
    """The script may NEVER run a real publish (our engineering rules + §40)."""

    source = (REPO_ROOT / "scripts/release/dry_run_npm.py").read_text(encoding="utf-8")
    # The script may reference these strings inside `"npm publish --dry-run"`
    # and helpful prose; ban only the "live publish" forms.
    forbidden_substrings = (
        "pnpm publish",  # live publish form (the dry-run uses `npm publish --dry-run`)
        "npm_publish_live",
    )
    for needle in forbidden_substrings:
        assert needle not in source, (
            f"scripts/release/dry_run_npm.py must not reference {needle!r} — "
            "the dry-run never publishes live"
        )


def test_inspect_tarball_flags_forbidden_entries(tmp_path: Path) -> None:
    import tarfile

    from scripts.release import dry_run_npm

    tarball = tmp_path / "fake.tgz"
    with tarfile.open(tarball, "w:gz") as tf:
        for name in (
            "package/dist/.git/HEAD",
            "package/dist/foo.test.ts",
            "package/dist/bar.spec.js",
            "package/dist/baz.tsbuildinfo",
            "package/src/raw_source.ts",
        ):
            payload = b"\n"
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, fileobj=__import__("io").BytesIO(payload))

    hits = dry_run_npm.inspect_tarball(tarball)
    reasons = {reason for _, reason in hits}
    # At least one hit per forbidden category.
    assert "git directory leaked into npm tarball" in reasons
    assert "test source leaked into npm tarball" in reasons
    assert "spec compiled file leaked into npm tarball" in reasons
    assert "tsc build-info leaked into npm tarball" in reasons
    assert "raw .ts source leaked into npm tarball" in reasons


def test_inspect_tarball_allows_clean_dist(tmp_path: Path) -> None:
    import io
    import tarfile

    from scripts.release import dry_run_npm

    tarball = tmp_path / "clean.tgz"
    with tarfile.open(tarball, "w:gz") as tf:
        for name in (
            "package/dist/index.js",
            "package/dist/index.d.ts",
            "package/dist/index.js.map",
            "package/LICENSE",
            "package/README.md",
            "package/package.json",
        ):
            payload = b"\n"
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, fileobj=io.BytesIO(payload))

    hits = dry_run_npm.inspect_tarball(tarball)
    assert hits == []


def test_publish_workflow_uses_provenance_oidc() -> None:
    workflow = (REPO_ROOT / ".github/workflows/publish-npm.yml").read_text(encoding="utf-8")
    # OIDC for provenance.
    assert "id-token: write" in workflow
    assert "NPM_CONFIG_PROVENANCE: 'true'" in workflow
    assert "--provenance" in workflow
    assert "--access public" in workflow
    # No legacy `_authToken` / plaintext token committed to the workflow.
    assert "_authToken" not in workflow
    # Environment gate.
    assert "name: npm-release" in workflow


def test_publish_workflow_verifies_after_publish() -> None:
    workflow = (REPO_ROOT / ".github/workflows/publish-npm.yml").read_text(encoding="utf-8")
    assert "verify (npm view + version match)" in workflow
    assert "npm view @sentinelqa/ts-runtime@${VERSION} version" in workflow


@pytest.mark.slow
@pytest.mark.skipif(not _have("pnpm"), reason="pnpm not on PATH")
@pytest.mark.skipif(not _have("npm"), reason="npm not on PATH")
def test_dry_run_npm_succeeds_on_current_main(tmp_path: Path) -> None:
    """Full build + pack + npm publish --dry-run on the live tree."""

    out_dir = tmp_path / "npm-dry"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release.dry_run_npm",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0, "dry_run_npm must exit 0 on current main"
    assert "dry_run_npm: ok" in proc.stdout
