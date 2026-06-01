# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""PyPI publish dry-run.

Runs ``uv build --all-packages`` (via ``scripts.release.build_all``)
to produce every Python sdist + wheel under ``dist/``, then validates
each one against PyPI's metadata rules via ``twine check``. This
script does **not** upload anything — that is the owner-only
PyPI Trusted-Publisher step described in
``docs/release/publish-runbook.md``.

The script is the local pre-flight the owner runs before pushing the
``v*`` tag. It is also called by the CI gate
``tests/integration/release/test_pypi_dry_run.py`` so a regression in
metadata (missing ``project.urls``, malformed license, wheel naming
collision, etc.) fails CI on the current ``main`` instead of fizzling
out on PyPI during a tag push.

Exit codes
----------

* ``0`` — build + ``twine check`` both succeeded for every artifact.
* ``2`` — build step failed, OR ``twine check`` flagged at least one
 artifact, OR ``twine`` is not installed.
* ``5`` — ``uv`` is not installed (required to build).

Twine is invoked via ``uv run twine check dist/*`` so the project's
own venv resolves it. If twine is missing from the dev env the
script prints a clear remediation line.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_FAIL = 2
EXIT_DEP_MISSING = 5


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _build_artifacts(out_dir: Path) -> int:
    """Build every Python sdist + wheel into ``out_dir``.

    Returns 0 on success, EXIT_FAIL on build failure.
    """

    cmd = [
        sys.executable,
        "-m",
        "scripts.release.build_all",
        "--out-dir",
        str(out_dir),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    return EXIT_OK if proc.returncode == 0 else EXIT_FAIL


def _twine_check(dist: Path) -> int:
    """Run ``twine check`` on every Python artifact under ``dist``.

    ``twine check`` validates wheel + sdist metadata against PyPI's
    upload rules (long-description renderability, license metadata
    completeness, classifier validity, etc.). It is a strict gate.
    """

    py_artifacts = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    if not py_artifacts:
        print("dry_run_pypi: no Python artifacts to check", file=sys.stderr)
        return EXIT_FAIL

    cmd = ["uv", "run", "twine", "check", "--strict", *(str(p) for p in py_artifacts)]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return EXIT_FAIL
    return EXIT_OK


def run_dry_run(out_dir: Path) -> int:
    """End-to-end build + twine check. Returns a process exit code."""

    if not _have("uv"):
        print(
            "dry_run_pypi: uv is required but not on PATH; install from https://docs.astral.sh/uv/",
            file=sys.stderr,
        )
        return EXIT_DEP_MISSING

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rc = _build_artifacts(out_dir)
    if rc != EXIT_OK:
        print("dry_run_pypi: build step failed", file=sys.stderr)
        return rc

    rc = _twine_check(out_dir)
    if rc != EXIT_OK:
        print("dry_run_pypi: twine check failed (see stderr above)", file=sys.stderr)
        return rc

    py_count = len(list(out_dir.glob("*.whl"))) + len(list(out_dir.glob("*.tar.gz")))
    print(f"dry_run_pypi: ok — {py_count} Python artifact(s) passed twine check --strict")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PyPI publish dry-run: build + twine check; never uploads."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "dist",
        help="Output directory for built artifacts (default: dist/).",
    )
    args = parser.parse_args(argv)
    return run_dry_run(args.out_dir.resolve())


if __name__ == "__main__":
    sys.exit(main())
