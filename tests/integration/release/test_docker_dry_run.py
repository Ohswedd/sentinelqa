# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Docker publish dry-run gate.

The publish workflow at ``.github/workflows/publish-docker.yml``
builds + pushes a multi-arch image to Docker Hub on every ``v*``
tag push. This file enforces that:

* the publish Dockerfile lives at the documented path and carries
 the OCI annotations the runbook depends on (title, description,
 source URL, version, revision, licenses, vendor);
* the dry-run script exposes the documented API and exit codes;
* the dry-run script never invokes ``docker push`` / ``--push``;
* the workflow builds both amd64 + arm64 with provenance + SBOM and
 pushes the four required tags (``<version>`` / ``<minor>`` /
 ``latest`` / ``sha-<short>``);
* the verify job pulls the image, asserts both architectures are
 in the manifest, and runs ``sentinel --version`` inside the image.

The actual multi-arch build is slow and gated behind
``SENTINELQA_HAS_DOCKER=1`` so it does not block CI on hosts without
Docker BuildKit / QEMU.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "apps/cli/sentinel/runner/docker/Dockerfile.publish"
WORKFLOW = REPO_ROOT / ".github/workflows/publish-docker.yml"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def test_publish_dockerfile_exists() -> None:
    assert (
        DOCKERFILE.is_file()
    ), "apps/cli/sentinel/runner/docker/Dockerfile.publish must exist (Phase 36.04)"


def test_publish_dockerfile_has_oci_labels() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    required = (
        'LABEL org.opencontainers.image.title="SentinelQA published runner"',
        'LABEL org.opencontainers.image.source="https://github.com/Ohswedd/sentinelqa"',
        'LABEL org.opencontainers.image.licenses="Apache-2.0"',
        "LABEL org.opencontainers.image.vendor",
        'LABEL org.opencontainers.image.version="${SENTINEL_VERSION}"',
        'LABEL org.opencontainers.image.revision="${SOURCE_COMMIT}"',
        'LABEL org.opencontainers.image.created="${BUILD_DATE}"',
    )
    for needle in required:
        assert needle in text, f"Dockerfile.publish must carry {needle!r}"


def test_publish_dockerfile_installs_sentinelqa_cli() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    # The image must install the matching CLI version, end-to-end.
    assert "ARG SENTINEL_VERSION" in text
    assert "sentinelqa-cli==${SENTINEL_VERSION}" in text
    # It must require the build arg (no silent default).
    assert "SENTINEL_VERSION build-arg is required" in text


def test_publish_dockerfile_isolates_install_in_a_venv() -> None:
    """Avoid colliding with the system / consumer Python env."""

    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "python3 -m venv" in text
    assert "SENTINEL_VENV=/opt/sentinelqa" in text
    assert 'PATH="${SENTINEL_VENV}/bin:${PATH}"' in text


def test_dry_run_script_is_importable_and_typed() -> None:
    from scripts.release import dry_run_docker

    assert callable(dry_run_docker.run_dry_run)
    assert callable(dry_run_docker.main)
    # Exit codes are stable contract.
    assert dry_run_docker.EXIT_OK == 0
    assert dry_run_docker.EXIT_FAIL == 2
    assert dry_run_docker.EXIT_DEP_MISSING == 5
    # Defaults match the documented workflow.
    assert dry_run_docker.DEFAULT_PLATFORMS == "linux/amd64,linux/arm64"
    assert dry_run_docker.DEFAULT_IMAGE == "sentinelqa/runner"


def test_dry_run_script_never_pushes() -> None:
    """our engineering rules + §40: the agent never pushes; the dry-run never pushes."""

    source = (REPO_ROOT / "scripts/release/dry_run_docker.py").read_text(encoding="utf-8")
    # Hard-ban every push form. The script may reference "--no-push" — that
    # is the explicit opt-OUT of push, not a push form.
    forbidden = (
        "docker push",
        '"--push"',
        "'--push'",
        "push: true",
    )
    for needle in forbidden:
        assert needle not in source, (
            f"scripts/release/dry_run_docker.py must not reference {needle!r} — "
            "dry-runs never push"
        )
    # Must explicitly use --no-push.
    assert "--no-push" in source


def test_publish_workflow_builds_multi_arch_with_provenance() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "platforms: linux/amd64,linux/arm64" in workflow
    # v1.7.0 (phase 37): Buildx provenance is now `mode=max` (full claims)
    # and a signed Sigstore attestation is added by attest-build-provenance.
    assert "provenance: mode=max" in workflow
    assert "actions/attest-build-provenance" in workflow
    assert "sbom: true" in workflow
    assert "push: true" in workflow


def test_publish_workflow_pushes_four_tags() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for tag_pattern in (
        "sentinelqa/runner:${{ steps.meta.outputs.version }}",
        "sentinelqa/runner:${{ steps.meta.outputs.minor }}",
        "sentinelqa/runner:latest",
        "sentinelqa/runner:sha-${{ steps.meta.outputs.short_sha }}",
    ):
        assert tag_pattern in workflow, f"publish-docker.yml must push {tag_pattern}"


def test_publish_workflow_verifies_pull_manifest_and_run() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "docker pull sentinelqa/runner:" in workflow
    assert "docker manifest inspect sentinelqa/runner:" in workflow
    assert "docker run --rm sentinelqa/runner:${VERSION} sentinel --version" in workflow
    # Both architectures verified by name.
    assert '"architecture": "amd64"' in workflow
    assert '"architecture": "arm64"' in workflow


def test_publish_workflow_uses_docker_release_environment() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "name: docker-release" in workflow
    # Credentials come from approval-gated secrets.
    assert "secrets.DOCKERHUB_USERNAME" in workflow
    assert "secrets.DOCKERHUB_TOKEN" in workflow


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("SENTINELQA_HAS_DOCKER") != "1",
    reason="SENTINELQA_HAS_DOCKER=1 not set; multi-arch buildx dry-run skipped",
)
@pytest.mark.skipif(not _have("docker"), reason="docker not on PATH")
def test_dry_run_docker_builds_multi_arch_no_push() -> None:
    """Full multi-arch build via `docker buildx --no-push`.

    Slow tier + opt-in. Validates the published Dockerfile actually
    builds for both amd64 and arm64 with the current
    ``SENTINEL_VERSION`` (= apps/cli/pyproject.toml version).
    """

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release.dry_run_docker",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0, "dry_run_docker must exit 0 with docker + buildx available"
    assert "dry_run_docker: ok" in proc.stdout
