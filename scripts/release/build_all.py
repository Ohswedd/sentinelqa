"""Build every SentinelQA distributable into a single output directory.

Python sdist + wheel are produced via ``uv build --all-packages`` so the four
publishable workspace members (``sentinelqa``, ``sentinelqa-cli``,
``sentinelqa-engine``, ``sentinelqa-mcp``) share one build invocation.

The TypeScript runtime tarball is produced via ``pnpm --filter ... pack``
(``pnpm pack`` from inside the package directory). The build step first runs
``pnpm --filter ... build`` so the compiled ``dist/`` ships in the tarball.

The Docker runner image is opt-in (off by default) because docker may not be
available on every CI runner. Pass ``--docker`` to include it.

Usage
-----

.. code-block:: bash

    python -m scripts.release.build_all --out-dir dist/

    # With Docker runner image.
    python -m scripts.release.build_all --out-dir dist/ --docker

Exit codes
----------

* 0 — every requested artifact built successfully.
* 2 — at least one build step failed (the failing step's stderr is forwarded).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Artifact catalogue
# --------------------------------------------------------------------------- #


@dataclass
class BuildArtifacts:
    out_dir: Path
    python_wheels: list[Path] = field(default_factory=list)
    python_sdists: list[Path] = field(default_factory=list)
    ts_tarballs: list[Path] = field(default_factory=list)
    docker_image: str | None = None

    def all_files(self) -> list[Path]:
        return [*self.python_wheels, *self.python_sdists, *self.ts_tarballs]


# --------------------------------------------------------------------------- #
# Build steps
# --------------------------------------------------------------------------- #


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    """Forward a subprocess and raise with stderr on failure."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"command failed: {' '.join(cmd)}\n")
        if result.stdout:
            sys.stderr.write(f"  stdout:\n{result.stdout}\n")
        if result.stderr:
            sys.stderr.write(f"  stderr:\n{result.stderr}\n")
        raise subprocess.CalledProcessError(result.returncode, cmd)


def build_python_packages(
    out_dir: Path, *, root: Path = REPO_ROOT
) -> tuple[list[Path], list[Path]]:
    """Build all four publishable Python workspace members.

    Returns ``(wheels, sdists)``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _run(["uv", "build", "--all-packages", "--out-dir", str(out_dir)], cwd=root)
    wheels = sorted(out_dir.glob("*.whl"))
    sdists = sorted(out_dir.glob("*.tar.gz"))
    if not wheels or not sdists:
        raise RuntimeError(
            f"uv build produced no artifacts in {out_dir}: {list(out_dir.iterdir())}"
        )
    return wheels, sdists


def build_ts_tarball(out_dir: Path, *, root: Path = REPO_ROOT) -> Path:
    """Compile ``@sentinelqa/ts-runtime`` and pack it into ``out_dir``.

    Returns the tarball path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_dir = root / "packages" / "ts-runtime"
    _run(["pnpm", "--filter", "@sentinelqa/ts-runtime", "build"], cwd=root)
    _run(["pnpm", "pack", "--pack-destination", str(out_dir)], cwd=ts_dir)
    tarballs = sorted(out_dir.glob("sentinelqa-ts-runtime-*.tgz"))
    if not tarballs:
        raise RuntimeError(f"pnpm pack produced no tarball in {out_dir}: {list(out_dir.iterdir())}")
    return tarballs[-1]


def build_docker_image(*, root: Path = REPO_ROOT, tag: str = "sentinelqa/runner:dev") -> str | None:
    """Build the runner Docker image if docker is on PATH.

    Returns the image tag, or ``None`` if docker is unavailable.
    """
    if shutil.which("docker") is None:
        sys.stderr.write("docker not on PATH; skipping runner image build.\n")
        return None
    dockerfile = root / "apps" / "cli" / "sentinel" / "runner" / "docker" / "Dockerfile.runner"
    if not dockerfile.exists():
        raise RuntimeError(f"runner Dockerfile missing: {dockerfile}")
    _run(["docker", "build", "-t", tag, "-f", str(dockerfile), "."], cwd=root)
    return tag


def build_all(
    out_dir: Path,
    *,
    root: Path = REPO_ROOT,
    build_docker: bool = False,
    docker_tag: str = "sentinelqa/runner:dev",
) -> BuildArtifacts:
    """Build every distributable into ``out_dir``."""
    out_dir = out_dir.resolve()
    if out_dir.exists():
        # Clean any stale artifacts so re-builds are deterministic.
        for entry in out_dir.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = BuildArtifacts(out_dir=out_dir)
    wheels, sdists = build_python_packages(out_dir, root=root)
    artifacts.python_wheels = wheels
    artifacts.python_sdists = sdists
    artifacts.ts_tarballs = [build_ts_tarball(out_dir, root=root)]
    if build_docker:
        artifacts.docker_image = build_docker_image(root=root, tag=docker_tag)
    return artifacts


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build every SentinelQA distributable.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "dist",
        help="Output directory for all artifacts. Default: ./dist",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Also build the runner Docker image.",
    )
    parser.add_argument(
        "--docker-tag",
        default="sentinelqa/runner:dev",
        help="Tag for the runner Docker image. Default: sentinelqa/runner:dev",
    )
    args = parser.parse_args(argv)

    try:
        artifacts = build_all(
            args.out_dir,
            build_docker=args.docker,
            docker_tag=args.docker_tag,
        )
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        sys.stderr.write(f"build-all failed: {exc}\n")
        return 2

    sys.stdout.write(f"built {len(artifacts.all_files())} artifact(s) into {artifacts.out_dir}:\n")
    for path in artifacts.all_files():
        sys.stdout.write(f"  {path.name}\n")
    if artifacts.docker_image:
        sys.stdout.write(f"  docker: {artifacts.docker_image}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
