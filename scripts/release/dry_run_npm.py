# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""npm publish dry-run.

Runs ``pnpm --filter @sentinelqa/ts-runtime build`` to produce the
compiled ``dist/`` tree, then exercises ``pnpm pack`` and
``npm publish --dry-run`` to validate that:

1. The tarball builds at all.
2. The tarball does NOT contain any forbidden contents (``.git/``,
 ``.env``, ``node_modules/``, source ``.test.ts``, ``.spec.ts``,
 source maps that should be inlined, etc.).
3. ``npm publish --dry-run`` does not error out (registry-side
 validation: name uniqueness scope, files: whitelist coherence).

This script never publishes — that is the owner-only step in
``docs/release/publish-runbook.md``.

Exit codes
----------

* ``0`` — build + pack + dry-run succeeded; tarball clean.
* ``2`` — one of the above steps failed, OR the tarball contained a
 forbidden file.
* ``5`` — ``pnpm`` or ``npm`` is not on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_PACKAGE_DIR = REPO_ROOT / "packages" / "ts-runtime"

EXIT_OK = 0
EXIT_FAIL = 2
EXIT_DEP_MISSING = 5

# Each entry is a (path-fragment, human-reason) pair. We check by
# substring match across every tarball entry's name so we catch both
# ``.git/HEAD`` and ``package/.git/HEAD``.
FORBIDDEN_TARBALL_ENTRIES: tuple[tuple[str, str], ...] = (
    (".git/", "git directory leaked into npm tarball"),
    (".env", "dotenv file leaked into npm tarball"),
    ("node_modules/", "node_modules leaked into npm tarball"),
    (".test.ts", "test source leaked into npm tarball"),
    (".test.js", "test compiled file leaked into npm tarball"),
    (".spec.ts", "spec source leaked into npm tarball"),
    (".spec.js", "spec compiled file leaked into npm tarball"),
    ("__tests__/", "tests directory leaked into npm tarball"),
    (".tsbuildinfo", "tsc build-info leaked into npm tarball"),
    # Source `.ts` files (NOT `.d.ts`) — the v1 publish ships dist/ only.
    # We allow `.d.ts` (type declarations).
)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(cmd: list[str], cwd: Path) -> int:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def _build_ts_runtime() -> int:
    print("dry_run_npm: building @sentinelqa/ts-runtime ...")
    return _run(
        ["pnpm", "--filter", "@sentinelqa/ts-runtime", "build"],
        cwd=REPO_ROOT,
    )


def _pnpm_pack(out_dir: Path) -> Path | None:
    """Run ``pnpm pack`` into ``out_dir`` and return the tarball path."""

    print(f"dry_run_npm: packing into {out_dir} ...")
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["pnpm", "pack", "--pack-destination", str(out_dir)],
        cwd=TS_PACKAGE_DIR,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return None
    tarballs = sorted(out_dir.glob("*.tgz"))
    return tarballs[-1] if tarballs else None


def _npm_publish_dry_run() -> int:
    print("dry_run_npm: running `npm publish --dry-run` ...")
    return _run(
        ["npm", "publish", "--dry-run", "--access", "public"],
        cwd=TS_PACKAGE_DIR,
    )


def inspect_tarball(tarball: Path) -> list[tuple[str, str]]:
    """Return a list of ``(member_name, reason)`` pairs for forbidden entries."""

    hits: list[tuple[str, str]] = []
    with tarfile.open(tarball, "r:gz") as tf:
        for member in tf.getmembers():
            name = member.name
            for fragment, reason in FORBIDDEN_TARBALL_ENTRIES:
                if fragment in name:
                    hits.append((name, reason))
            # Source.ts files (other than.d.ts) — extra rule that does
            # not fit the simple "substring" pattern above.
            if name.endswith(".ts") and not name.endswith(".d.ts"):
                hits.append((name, "raw .ts source leaked into npm tarball"))
    return hits


def run_dry_run(out_dir: Path) -> int:
    if not _have("pnpm"):
        print("dry_run_npm: pnpm not on PATH (install via corepack or npm)", file=sys.stderr)
        return EXIT_DEP_MISSING
    if not _have("npm"):
        print("dry_run_npm: npm not on PATH", file=sys.stderr)
        return EXIT_DEP_MISSING

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if _build_ts_runtime() != 0:
        print("dry_run_npm: build failed", file=sys.stderr)
        return EXIT_FAIL

    tarball = _pnpm_pack(out_dir)
    if tarball is None:
        print("dry_run_npm: pnpm pack produced no tarball", file=sys.stderr)
        return EXIT_FAIL

    print(f"dry_run_npm: inspecting {tarball.name} ...")
    hits = inspect_tarball(tarball)
    if hits:
        print(f"dry_run_npm: tarball {tarball.name} contains forbidden entries:", file=sys.stderr)
        for name, reason in hits:
            print(f"  {name}  ({reason})", file=sys.stderr)
        return EXIT_FAIL

    if _npm_publish_dry_run() != 0:
        print("dry_run_npm: `npm publish --dry-run` failed", file=sys.stderr)
        return EXIT_FAIL

    print(f"dry_run_npm: ok — {tarball.name} packs cleanly and passes `npm publish --dry-run`")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="npm publish dry-run for @sentinelqa/ts-runtime; never publishes."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "dist" / "npm-dry-run",
        help="Output directory for the packed tarball (default: dist/npm-dry-run/).",
    )
    args = parser.parse_args(argv)
    return run_dry_run(args.out_dir.resolve())


if __name__ == "__main__":
    sys.exit(main())
