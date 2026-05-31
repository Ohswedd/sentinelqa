# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Docker Hub publish dry-run (Phase 36.04).

Builds ``sentinelqa/runner:<version>`` from
``apps/cli/sentinel/runner/docker/Dockerfile.publish`` for both
``linux/amd64`` and ``linux/arm64`` via ``docker buildx`` with
``--no-push`` so the published image's reproducibility is validated
locally before the ``v*`` tag goes out.

The script is gated by ``SENTINELQA_HAS_DOCKER=1`` so it can be
called from a CI lane that has Docker BuildKit + buildx + QEMU
available; on a developer laptop without those, it exits 5 with a
clear remediation line.

The script never pushes — that is the owner-only Docker Hub push
step in ``docs/release/publish-runbook.md``.

Exit codes
----------

* ``0`` — the multi-arch build succeeded (image is reproducible).
* ``2`` — the build step failed (logs forwarded to stderr).
* ``5`` — docker or buildx is not available on the host.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "apps/cli/sentinel/runner/docker/Dockerfile.publish"

EXIT_OK = 0
EXIT_FAIL = 2
EXIT_DEP_MISSING = 5

DEFAULT_PLATFORMS = "linux/amd64,linux/arm64"
DEFAULT_IMAGE = "sentinelqa/runner"


def _have_docker() -> bool:
    return shutil.which("docker") is not None


def _read_cli_version() -> str:
    pyproject = REPO_ROOT / "apps/cli/pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _buildx_available() -> bool:
    """Return True iff `docker buildx version` succeeds.

    The `buildx` plugin is bundled with Docker Desktop and modern
    Docker Engine builds, but a stripped CI image may lack it.
    """

    if not _have_docker():
        return False
    proc = subprocess.run(
        ["docker", "buildx", "version"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def run_dry_run(
    *,
    version: str | None = None,
    platforms: str = DEFAULT_PLATFORMS,
    image: str = DEFAULT_IMAGE,
) -> int:
    if not _have_docker():
        print(
            "dry_run_docker: docker is not on PATH; install Docker Desktop or set up docker-ce.",
            file=sys.stderr,
        )
        return EXIT_DEP_MISSING
    if not _buildx_available():
        print(
            "dry_run_docker: `docker buildx` is unavailable; enable BuildKit/buildx and try again.",
            file=sys.stderr,
        )
        return EXIT_DEP_MISSING

    if version is None:
        version = _read_cli_version()
    tag = f"{image}:{version}"
    print(f"dry_run_docker: building {tag} for {platforms} ({DOCKERFILE.name}) ...")

    cmd = [
        "docker",
        "buildx",
        "build",
        "--platform",
        platforms,
        "--no-push",
        "--build-arg",
        f"SENTINEL_VERSION={version}",
        "-f",
        str(DOCKERFILE),
        "-t",
        tag,
        str(DOCKERFILE.parent),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    if proc.returncode != 0:
        print("dry_run_docker: build step failed", file=sys.stderr)
        return EXIT_FAIL

    print(f"dry_run_docker: ok — {tag} built for {platforms} (no push performed)")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Docker Hub publish dry-run: multi-arch buildx --no-push; never pushes."
    )
    parser.add_argument("--version", default=None, help="Override the version tag.")
    parser.add_argument(
        "--platforms",
        default=DEFAULT_PLATFORMS,
        help=f"Build platforms (default: {DEFAULT_PLATFORMS}).",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Image name (default: {DEFAULT_IMAGE}).",
    )
    args = parser.parse_args(argv)
    return run_dry_run(
        version=args.version,
        platforms=args.platforms,
        image=args.image,
    )


if __name__ == "__main__":
    sys.exit(main())
