# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Post-publish smoke.

The owner runs these four assertions **after** a real publish
(``v*`` tag pushed; PyPI / npm / Docker Hub / GitHub Release
workflows green) to verify the public artifacts actually work:

1. ``uv pip install sentinelqa-cli==<tag>`` from PyPI into a
 fresh venv; ``sentinel --version`` reports ``<tag>``.
2. ``pnpm install @sentinelqa/ts-runtime@<tag>`` into a fresh
 project; ``require('@sentinelqa/ts-runtime')`` succeeds.
3. ``docker pull sentinelqa/runner:<tag>`` + ``docker run --rm
 sentinelqa/runner:<tag> sentinel --version`` reports ``<tag>``.
4. ``docker manifest inspect sentinelqa/runner:<tag>`` shows
 both ``linux/amd64`` and ``linux/arm64``.

The whole file is gated by ``SENTINELQA_TEST_POST_PUBLISH=1``
because every test reaches a public registry and the v0.x line
predates the registries entirely. The publish-runbook calls this
test as the "verify" step.

The tag is read from ``apps/cli/pyproject.toml`` so a future bump
does not need to touch this file. Run as::

 SENTINELQA_TEST_POST_PUBLISH=1 uv run pytest \\
 tests/integration/release/test_post_publish_smoke.py -v

The tests are also runnable against the local ``dist/`` directory
(by the publish workflows' "build" job) — when invoked with
``SENTINELQA_POST_PUBLISH_LOCAL_DIST=<dir>`` the PyPI assertion
installs from that local index instead of pypi.org so the smoke
can run before the actual publish lands.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- #
# Gating + helpers
# --------------------------------------------------------------------------- #


_POST_PUBLISH_GATE = pytest.mark.skipif(
    os.environ.get("SENTINELQA_TEST_POST_PUBLISH") != "1",
    reason="SENTINELQA_TEST_POST_PUBLISH=1 not set; post-publish smoke skipped",
)


def _read_published_version() -> str:
    pyproject = REPO_ROOT / "apps/cli/pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    version = data["project"]["version"]
    assert isinstance(version, str)
    return version


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _local_dist_dir() -> Path | None:
    """Optional override: install from a local dist directory."""

    dist = os.environ.get("SENTINELQA_POST_PUBLISH_LOCAL_DIST")
    if not dist:
        return None
    p = Path(dist)
    if not p.is_dir():
        pytest.skip(f"SENTINELQA_POST_PUBLISH_LOCAL_DIST={dist} is not a directory")
    return p


# --------------------------------------------------------------------------- #
# 1. PyPI
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@_POST_PUBLISH_GATE
@pytest.mark.skipif(not _have("uv"), reason="uv not on PATH")
def test_pypi_install_and_sentinel_version(tmp_path: Path) -> None:
    version = _read_published_version()
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", str(venv), "--python", "3.12"], check=True)

    install_cmd = [
        "uv",
        "pip",
        "install",
        "--python",
        str(venv / "bin" / "python"),
    ]
    local_dist = _local_dist_dir()
    if local_dist:
        install_cmd += [
            "--no-index",
            "--find-links",
            str(local_dist),
            f"sentinelqa-cli=={version}",
        ]
    else:
        install_cmd += [
            "--index-url",
            "https://pypi.org/simple",
            "--index-strategy",
            "unsafe-best-match",
            f"sentinelqa-cli=={version}",
        ]
    subprocess.run(install_cmd, check=True)

    result = subprocess.run(
        [str(venv / "bin" / "sentinel"), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    out = (result.stdout + result.stderr).strip()
    assert version in out, f"sentinel --version did not report {version}; got:\n{out}"


# --------------------------------------------------------------------------- #
# 2. npm
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@_POST_PUBLISH_GATE
@pytest.mark.skipif(not _have("npm"), reason="npm not on PATH")
def test_npm_install_and_require_succeeds(tmp_path: Path) -> None:
    version = _read_published_version()

    # Bootstrap a tiny throwaway project that consumes the published
    # package via npm (NOT pnpm — that keeps this test from depending
    # on a pnpm workspace lockfile).
    project = tmp_path / "consumer"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "sentinel-post-publish-smoke",
                "version": "0.0.0",
                "type": "module",
                "private": True,
            }
        ),
        encoding="utf-8",
    )

    local_tarball_env = os.environ.get("SENTINELQA_POST_PUBLISH_NPM_TARBALL")
    if local_tarball_env:
        tarball = Path(local_tarball_env)
        if not tarball.is_file():
            pytest.skip(f"SENTINELQA_POST_PUBLISH_NPM_TARBALL={tarball} is not a file")
        install_target = str(tarball)
    else:
        install_target = f"@sentinelqa/ts-runtime@{version}"

    subprocess.run(
        ["npm", "install", install_target],
        cwd=project,
        check=True,
        capture_output=True,
    )

    # `require()` smoke — ESM-import the package via Node's default
    # loader. If the package's exports map is broken this fails loud.
    smoke = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import('@sentinelqa/ts-runtime').then(m => "
            "{ if (typeof m !== 'object') { process.exit(1); } });",
        ],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert smoke.returncode == 0


# --------------------------------------------------------------------------- #
# 3 + 4. Docker
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@_POST_PUBLISH_GATE
@pytest.mark.skipif(not _have("docker"), reason="docker not on PATH")
def test_docker_pull_run_and_multi_arch_manifest() -> None:
    version = _read_published_version()
    image = f"sentinelqa/runner:{version}"

    subprocess.run(["docker", "pull", image], check=True)

    run = subprocess.run(
        ["docker", "run", "--rm", image, "sentinel", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert version in (run.stdout + run.stderr), (
        f"sentinel --version inside {image} did not report {version}; "
        f"got:\n{run.stdout}\n{run.stderr}"
    )

    manifest = subprocess.run(
        ["docker", "manifest", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest_text = manifest.stdout
    assert (
        '"architecture": "amd64"' in manifest_text
    ), f"{image} manifest does not include linux/amd64"
    assert (
        '"architecture": "arm64"' in manifest_text
    ), f"{image} manifest does not include linux/arm64"


# --------------------------------------------------------------------------- #
# Health check — the gating sentinel itself runs even outside the gate.
# --------------------------------------------------------------------------- #


def test_gating_env_var_documented_in_publish_runbook() -> None:
    """The runbook must name the env var that unlocks this smoke test
    so the owner doesn't have to grep the test to find it."""

    if not (REPO_ROOT / "docs/release/publish-runbook.md").is_file():
        pytest.skip("publish-runbook.md is wired in Phase 36.07")
    runbook = (REPO_ROOT / "docs/release/publish-runbook.md").read_text(encoding="utf-8")
    assert "SENTINELQA_TEST_POST_PUBLISH=1" in runbook
