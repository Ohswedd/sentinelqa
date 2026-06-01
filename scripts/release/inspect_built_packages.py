"""Inspect built SentinelQA distributables for forbidden contents.

Walks every artifact under ``dist/`` (wheels, sdists, npm tarballs) and asserts
that no Python wheel, sdist, or npm tarball ships:

* a ``.git/`` directory
* a ``.env`` file (secrets)
* private-key files (``*.pem``, ``*.key``, ``id_rsa*``)
* cloud-credential blobs (``credentials*``, ``service-account*.json``)
* compiled Python caches (``__pycache__/``, ``*.pyc``)

Optionally also lists the resolved file inventory for each artifact for a human
sanity review (the spec phrases this as "inspect contents of
every built artifact for a sanity review").

Exit codes
----------

* 0 — every artifact is clean.
* 2 — at least one artifact contains a forbidden file.
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Forbidden patterns
# --------------------------------------------------------------------------- #

# Each entry is a compiled regex tested against the POSIX-form member path.
# A match means "this file must NOT be in a release artifact".
FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("git_directory", re.compile(r"(^|/)\.git(/|$)")),
    ("dotenv_file", re.compile(r"(^|/)\.env(?:\.|$)")),
    ("private_key_pem", re.compile(r"(^|/).*\.pem$")),
    ("private_key_key", re.compile(r"(^|/).*\.key$")),
    ("private_key_p12", re.compile(r"(^|/).*\.p12$")),
    ("private_key_pfx", re.compile(r"(^|/).*\.pfx$")),
    ("ssh_id_rsa", re.compile(r"(^|/)id_rsa(\.|$)")),
    ("ssh_id_ed25519", re.compile(r"(^|/)id_ed25519(\.|$)")),
    ("ssh_id_ecdsa", re.compile(r"(^|/)id_ecdsa(\.|$)")),
    (
        "cloud_creds",
        re.compile(r"(^|/)(credentials|service-account[^/]*)\.(json|yaml|yml)$"),
    ),
    ("py_cache_dir", re.compile(r"(^|/)__pycache__(/|$)")),
    ("py_cache_pyc", re.compile(r"(^|/).*\.pyc$")),
    ("hidden_aws", re.compile(r"(^|/)\.aws(/|$)")),
    ("hidden_gcloud", re.compile(r"(^|/)\.gcloud(/|$)")),
)


# --------------------------------------------------------------------------- #
# Listing artifacts
# --------------------------------------------------------------------------- #


def list_wheel_members(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def list_sdist_members(path: Path) -> list[str]:
    with tarfile.open(path, mode="r:gz") as tf:
        return tf.getnames()


def list_ts_tarball_members(path: Path) -> list[str]:
    with tarfile.open(path, mode="r:gz") as tf:
        return tf.getnames()


def list_members(path: Path) -> list[str]:
    name = path.name
    if name.endswith(".whl"):
        return list_wheel_members(path)
    if name.endswith(".tar.gz"):
        return list_sdist_members(path)
    if name.endswith(".tgz"):
        return list_ts_tarball_members(path)
    raise ValueError(f"unknown artifact extension: {path}")


# --------------------------------------------------------------------------- #
# Inspecting an artifact
# --------------------------------------------------------------------------- #


def find_forbidden(members: Iterable[str]) -> list[tuple[str, str]]:
    """Return ``(reason, member)`` pairs for each forbidden hit."""
    hits: list[tuple[str, str]] = []
    for member in members:
        # Normalise to POSIX form so regex patterns work cross-platform.
        normalised = member.replace("\\", "/")
        for reason, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(normalised):
                hits.append((reason, member))
                break  # one finding per member is enough
    return hits


def inspect_artifact(path: Path) -> list[tuple[str, str]]:
    """Inspect one artifact. Returns a list of ``(reason, member)`` failures."""
    return find_forbidden(list_members(path))


def inspect_all(dist_dir: Path) -> dict[Path, list[tuple[str, str]]]:
    """Inspect every artifact in ``dist_dir``."""
    failures: dict[Path, list[tuple[str, str]]] = {}
    for path in sorted(dist_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix not in {".whl", ".tgz", ".gz"} and not path.name.endswith(".tar.gz"):
            continue
        hits = inspect_artifact(path)
        if hits:
            failures[path] = hits
    return failures


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect built SentinelQA distributables.")
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=REPO_ROOT / "dist",
        help="Directory containing built artifacts. Default: ./dist",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Also print the file inventory for every artifact (human sanity review).",
    )
    args = parser.parse_args(argv)

    if not args.dist_dir.is_dir():
        sys.stderr.write(f"dist directory missing: {args.dist_dir}\n")
        return 2

    failures = inspect_all(args.dist_dir)

    if args.list:
        for path in sorted(args.dist_dir.iterdir()):
            if not path.is_file():
                continue
            try:
                members = list_members(path)
            except ValueError:
                continue
            sys.stdout.write(f"=== {path.name} ({len(members)} files) ===\n")
            for m in members:
                sys.stdout.write(f"  {m}\n")

    if failures:
        sys.stderr.write(f"inspect: {sum(len(v) for v in failures.values())} forbidden file(s):\n")
        for path, hits in failures.items():
            sys.stderr.write(f"  {path.name}:\n")
            for reason, member in hits:
                sys.stderr.write(f"    [{reason}] {member}\n")
        return 2

    n = sum(
        1
        for p in args.dist_dir.iterdir()
        if p.is_file() and (p.suffix in {".whl", ".tgz"} or p.name.endswith(".tar.gz"))
    )
    sys.stdout.write(f"inspect: ok — {n} artifact(s) inspected, no forbidden files\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
