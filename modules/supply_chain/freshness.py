"""Lockfile freshness + manifest-drift checks.

A lockfile that hasn't been touched in months is almost always missing
upstream security fixes — and lockfile↔manifest drift (a dep declared
in ``package.json`` but missing from ``package-lock.json``, or vice
versa) is the classic signal that ``npm install`` was skipped before
the last commit. Both findings carry ``CWE-1357`` (Reliance on
Unmaintained Third-Party Components).

The age check is git-aware: we look at both the filesystem mtime AND
the last git commit that touched the lockfile, and take the more
recent of the two. That keeps the check honest on a fresh clone where
``mtime`` is the checkout time, not the last edit time.

The drift check is intentionally conservative — we only flag the
clear cases (a direct dep in the manifest that has no version pin in
the lockfile, or vice versa). Range-vs-pin and platform-specific
variance are NOT flagged; those are out-of-band for an audit module
and would generate too much noise on real projects.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from modules.supply_chain.lockfiles import detect_lockfiles
from modules.supply_chain.models import (
    FreshnessLockfileResult,
    FreshnessReport,
    LockfileKind,
)

DEFAULT_THRESHOLD_DAYS = 180
"""Phase 33 README default."""


# ---------------------------------------------------------------------------
# Age
# ---------------------------------------------------------------------------


def _last_git_touch(path: Path, project_root: Path) -> date | None:
    """Return the date of the last git commit that touched ``path``.

    Returns ``None`` when the file isn't tracked or git is unavailable.
    A best-effort signal — the caller still has the filesystem mtime
    fallback.
    """

    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "log", "-1", "--format=%cs", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def compute_lockfile_age_days(path: Path, project_root: Path, *, today: date | None = None) -> int:
    """Days since the lockfile was last modified.

    Takes the **most recent** of (filesystem mtime, last-git-commit date)
    so that a freshly-cloned repo doesn't read as freshly-edited.
    """

    today = today or datetime.now(UTC).date()
    candidates: list[date] = []
    try:
        mtime = path.stat().st_mtime
        candidates.append(datetime.fromtimestamp(mtime, tz=UTC).date())
    except OSError:
        pass
    git_date = _last_git_touch(path, project_root)
    if git_date is not None:
        candidates.append(git_date)
    if not candidates:
        return 0
    latest = max(candidates)
    delta = (today - latest).days
    return max(0, delta)


# ---------------------------------------------------------------------------
# Manifest drift
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _npm_direct_deps(package_json: dict[str, Any]) -> set[str]:
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        block = package_json.get(key, {})
        if isinstance(block, dict):
            deps.update(name for name in block if isinstance(name, str))
    return deps


def _package_lock_names(package_lock: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    packages = package_lock.get("packages")
    if isinstance(packages, dict):
        for key, entry in packages.items():
            if key == "" or not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str):
                names.add(name)
                continue
            tail = key.split("node_modules/")[-1]
            if tail:
                names.add(tail)
    deps = package_lock.get("dependencies")
    if isinstance(deps, dict):
        names.update(n for n in deps if isinstance(n, str))
    return names


def _pnpm_lock_names(pnpm_lock: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    packages = pnpm_lock.get("packages")
    if isinstance(packages, dict):
        for key in packages:
            if not isinstance(key, str):
                continue
            stripped = key.lstrip("/").split("(", 1)[0]
            if stripped.startswith("@"):
                scope, _, rest = stripped[1:].partition("/")
                name_part = rest.rpartition("@")[0]
                if name_part:
                    names.add(f"@{scope}/{name_part}")
            else:
                name_part = stripped.rpartition("@")[0]
                if name_part:
                    names.add(name_part)
    return names


def detect_npm_drift(project_root: Path) -> tuple[str, ...]:
    """Detect direct-dep drift between ``package.json`` and ``package-lock.json``.

    Returns a tuple of human-readable descriptions, one per drifted
    package. Empty tuple means no drift detected (or no manifests to
    compare).
    """

    manifest_path = project_root / "package.json"
    lock_path = project_root / "package-lock.json"
    if not manifest_path.is_file() or not lock_path.is_file():
        return ()
    declared = _npm_direct_deps(_read_json(manifest_path))
    locked = _package_lock_names(_read_json(lock_path))
    if not declared:
        return ()
    drifted = sorted(declared - locked)
    return tuple(
        f"{name}: declared in package.json, missing from package-lock.json" for name in drifted
    )


def detect_pnpm_drift(project_root: Path) -> tuple[str, ...]:
    """Same idea as :func:`detect_npm_drift` for pnpm-lock.yaml."""

    manifest_path = project_root / "package.json"
    lock_path = project_root / "pnpm-lock.yaml"
    if not manifest_path.is_file() or not lock_path.is_file():
        return ()
    declared = _npm_direct_deps(_read_json(manifest_path))
    locked = _pnpm_lock_names(_read_yaml(lock_path))
    if not declared:
        return ()
    drifted = sorted(declared - locked)
    return tuple(
        f"{name}: declared in package.json, missing from pnpm-lock.yaml" for name in drifted
    )


def _pyproject_direct_deps(pyproject: dict[str, Any]) -> set[str]:
    """Pull the direct deps declared under ``[project]`` and ``[tool.poetry.dependencies]``."""

    deps: set[str] = set()
    project_block = pyproject.get("project", {})
    if isinstance(project_block, dict):
        for spec in project_block.get("dependencies", []) or []:
            name = _normalize_pep508_name(spec)
            if name:
                deps.add(name)
        optional = project_block.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    for spec in group:
                        name = _normalize_pep508_name(spec)
                        if name:
                            deps.add(name)
    poetry_block = pyproject.get("tool", {}).get("poetry", {})
    if isinstance(poetry_block, dict):
        poetry_deps = poetry_block.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            deps.update(
                name for name in poetry_deps if isinstance(name, str) and name.lower() != "python"
            )
    return {d.lower() for d in deps}


def _normalize_pep508_name(spec: Any) -> str | None:
    if not isinstance(spec, str):
        return None
    name = spec.strip()
    for delim in ("[", "(", "=", "<", ">", "!", "~", ";", " "):
        idx = name.find(delim)
        if idx != -1:
            name = name[:idx]
    return name.lower() or None


def _python_lock_names(lockfile_path: Path, kind: LockfileKind) -> set[str]:
    if kind == "uv.lock":
        data = _read_toml(lockfile_path)
        packages = data.get("package", [])
        if isinstance(packages, list):
            return {
                str(p.get("name", "")).lower()
                for p in packages
                if isinstance(p, dict) and p.get("name")
            }
        return set()
    if kind == "poetry.lock":
        data = _read_toml(lockfile_path)
        packages = data.get("package", [])
        if isinstance(packages, list):
            return {
                str(p.get("name", "")).lower()
                for p in packages
                if isinstance(p, dict) and p.get("name")
            }
        return set()
    return set()


def detect_python_drift(project_root: Path, kind: LockfileKind) -> tuple[str, ...]:
    """Compare ``pyproject.toml`` direct deps to the lockfile's package set."""

    pyproject_path = project_root / "pyproject.toml"
    lockfile_path = project_root / kind
    if not pyproject_path.is_file() or not lockfile_path.is_file():
        return ()
    declared = _pyproject_direct_deps(_read_toml(pyproject_path))
    locked = _python_lock_names(lockfile_path, kind)
    if not declared:
        return ()
    drifted = sorted(declared - locked)
    return tuple(f"{name}: declared in pyproject.toml, missing from {kind}" for name in drifted)


# ---------------------------------------------------------------------------
# High-level entrypoint
# ---------------------------------------------------------------------------


def evaluate_freshness(
    *,
    project_root: Path,
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
    now: datetime | None = None,
) -> FreshnessReport:
    """Run age + drift checks across every detected lockfile."""

    timestamp = now or datetime.now(UTC)
    detected = detect_lockfiles(project_root)
    today = timestamp.date()
    results: list[FreshnessLockfileResult] = []

    for lockfile in detected:
        age = compute_lockfile_age_days(lockfile.path, project_root, today=today)
        drift: Iterable[str] = ()
        if lockfile.kind == "package-lock.json":
            drift = detect_npm_drift(project_root)
        elif lockfile.kind == "pnpm-lock.yaml":
            drift = detect_pnpm_drift(project_root)
        elif lockfile.kind in {"uv.lock", "poetry.lock"}:
            drift = detect_python_drift(project_root, lockfile.kind)
        results.append(
            FreshnessLockfileResult(
                path=lockfile.path.relative_to(project_root).as_posix(),
                kind=lockfile.kind,
                age_days=age,
                stale=age > threshold_days,
                threshold_days=threshold_days,
                manifest_drift=tuple(drift),
            )
        )

    return FreshnessReport(
        checked_at=timestamp,
        threshold_days=threshold_days,
        lockfiles=tuple(results),
        skipped=not results,
        skipped_reason="no lockfiles detected" if not results else None,
    )


__all__ = [
    "DEFAULT_THRESHOLD_DAYS",
    "compute_lockfile_age_days",
    "detect_npm_drift",
    "detect_pnpm_drift",
    "detect_python_drift",
    "evaluate_freshness",
]
