# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Smart test selection — map a git diff to the set of audit modules.

The user opt-in is ``sentinel audit --changed-only``. The CLI calls
:func:`changed_files_against` to obtain the list of changed files
relative to a base ref (typically ``origin/main``), feeds them into
:func:`impacted_modules`, and passes the resulting module set to the
lifecycle as ``requested_modules``.

The mapping is intentionally generous on the "config files" axis: a
change to ``next.config.ts``, ``vite.config.*``, ``astro.config.*``,
the package manifest, or any lockfile invalidates the entire module
set. This preserves correctness — config drift can affect every module
— while still skipping the audit altogether when only docs or unrelated
files change.

All paths are matched on POSIX-normalised relative paths so behaviour
is identical on macOS, Linux and Windows.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Canonical module names — kept in lock-step with the registry. Order
# matters only for the "all modules" path so the resulting frozenset is
# stable for tests.
ALL_MODULES: frozenset[str] = frozenset(
    {
        "functional",
        "a11y",
        "perf",
        "security",
        "api",
        "visual",
        "chaos",
        "llm_audit",
        "supply_chain",
    }
)

# Patterns that invalidate the *entire* module set. Build / framework
# configs and lockfiles are in this bucket because they can change any
# module's behaviour without changing the source they audit.
_GLOBAL_INVALIDATORS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"(^|/)package\.json$",
        r"(^|/)package-lock\.json$",
        r"(^|/)pnpm-lock\.yaml$",
        r"(^|/)yarn\.lock$",
        r"(^|/)pyproject\.toml$",
        r"(^|/)uv\.lock$",
        r"(^|/)requirements.*\.txt$",
        r"(^|/)Pipfile\.lock$",
        r"(^|/)tsconfig.*\.json$",
        r"(^|/)next\.config\.[^/]+$",
        r"(^|/)nuxt\.config\.[^/]+$",
        r"(^|/)astro\.config\.[^/]+$",
        r"(^|/)vite\.config\.[^/]+$",
        r"(^|/)svelte\.config\.[^/]+$",
        r"(^|/)remix\.config\.[^/]+$",
        r"(^|/)sentinel\.config\.ya?ml$",
        r"(^|/)\.github/workflows/[^/]+\.ya?ml$",
        r"(^|/)Dockerfile(\.[^/]+)?$",
    )
)

# Per-module pattern table. Keys are module names; values are tuples of
# regexes that, when ANY matches a changed file, mark that module
# impacted. Order doesn't matter — the union of matches is returned.
_MODULE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "functional": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte|mjs|cjs)$",
            r"(^|/)pages/",
            r"(^|/)app/(?!api/)",
            r"(^|/)src/",
            r"(^|/)routes/",
            r"(^|/)components/",
        )
    ),
    "a11y": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte|html|css|scss)$",
            r"(^|/)components/",
            r"(^|/)pages/",
            r"(^|/)src/",
            r"(^|/)styles/",
        )
    ),
    "visual": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte|css|scss|html|module\.css)$",
            r"(^|/)components/",
            r"(^|/)styles/",
            r"(^|/)pages/",
        )
    ),
    "perf": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte|html|css|scss)$",
            r"(^|/)pages/",
            r"(^|/)app/",
            r"(^|/)public/",
        )
    ),
    "api": tuple(
        re.compile(p)
        for p in (
            r"\.api\.tsx?$",
            r"(^|/)api/",
            r"(^|/)app/api/",
            r"(^|/)pages/api/",
            r"(^|/)routes/api/",
            r"(^|/)server/",
            r"\.py$",  # backend Python often hosts the API
            r"openapi.*\.(ya?ml|json)$",
            r"graphql.*\.(graphql|gql|ts)$",
        )
    ),
    "security": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|py)$",
            r"(^|/)middleware\.",
            r"(^|/)auth/",
            r"(^|/)security/",
            r"\.env(\.[^/]+)?$",
        )
    ),
    "chaos": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte)$",
            r"(^|/)src/",
            r"(^|/)app/",
        )
    ),
    "llm_audit": tuple(
        re.compile(p)
        for p in (
            r"\.(tsx?|jsx?|vue|svelte|py)$",
            r"(^|/)src/",
            r"(^|/)app/",
            r"(^|/)components/",
        )
    ),
    "supply_chain": tuple(
        re.compile(p)
        for p in (
            r"(^|/)package\.json$",
            r"(^|/)pnpm-lock\.yaml$",
            r"(^|/)yarn\.lock$",
            r"(^|/)package-lock\.json$",
            r"(^|/)pyproject\.toml$",
            r"(^|/)uv\.lock$",
            r"(^|/)requirements.*\.txt$",
            r"(^|/)Pipfile\.lock$",
            r"(^|/)Dockerfile(\.[^/]+)?$",
        )
    ),
}


@dataclass(frozen=True, slots=True)
class DiffSelection:
    """Result of mapping a diff to a set of impacted modules.

    ``all_invalidated`` is True when at least one changed file matched a
    global invalidator (config / lockfile / Dockerfile). In that case
    ``modules`` is the entire :data:`ALL_MODULES` set.
    """

    modules: frozenset[str]
    changed_files: tuple[Path, ...]
    all_invalidated: bool

    def empty(self) -> bool:
        return not self.modules


class GitNotAvailableError(RuntimeError):
    """Raised when ``git`` is not on PATH or the cwd is not a git repo."""


def changed_files_against(
    base_ref: str,
    *,
    cwd: Path | None = None,
    include_unstaged: bool = True,
    runner: object = None,
) -> tuple[Path, ...]:
    """Return the changed files relative to ``base_ref``.

    Three sources are unioned:

    - ``git diff --name-only <base_ref>...HEAD`` (committed changes
      between the merge base and HEAD);
    - ``git diff --name-only`` (unstaged tracked changes);
    - ``git ls-files --others --exclude-standard`` (new untracked
      files), included only when ``include_unstaged`` is true.

    Paths are returned as relative POSIX :class:`Path` objects. The
    function raises :class:`GitNotAvailableError` if ``git`` is missing
    or the cwd is not a git repo.

    ``runner`` is a test seam — if provided, it must be a callable with
    the same signature as :func:`subprocess.run`.
    """

    run = runner if runner is not None else subprocess.run
    work_dir = str(cwd) if cwd is not None else None

    def _git(*args: str) -> list[str]:
        try:
            result = run(  # type: ignore[operator]
                ["git", *args],
                cwd=work_dir,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise GitNotAvailableError("git is not on PATH") from exc
        if result.returncode != 0:
            raise GitNotAvailableError(
                f"git {' '.join(args)} failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return [line for line in result.stdout.splitlines() if line.strip()]

    files: set[str] = set()
    files.update(_git("diff", "--name-only", f"{base_ref}...HEAD"))
    if include_unstaged:
        files.update(_git("diff", "--name-only"))
        files.update(_git("ls-files", "--others", "--exclude-standard"))
    return tuple(sorted(Path(p) for p in files))


def _matches(path: Path, patterns: Iterable[re.Pattern[str]]) -> bool:
    posix = path.as_posix()
    return any(p.search(posix) for p in patterns)


def impacted_modules(changed: Iterable[Path]) -> DiffSelection:
    """Map a sequence of changed files to the set of impacted modules.

    Pure function — no IO. Tests pass a synthetic list of paths.
    """

    files = tuple(changed)
    if not files:
        return DiffSelection(modules=frozenset(), changed_files=(), all_invalidated=False)

    if any(_matches(p, _GLOBAL_INVALIDATORS) for p in files):
        return DiffSelection(modules=ALL_MODULES, changed_files=files, all_invalidated=True)

    matched: set[str] = set()
    for module_name, patterns in _MODULE_PATTERNS.items():
        if any(_matches(p, patterns) for p in files):
            matched.add(module_name)
    return DiffSelection(modules=frozenset(matched), changed_files=files, all_invalidated=False)


def select_modules(
    base_ref: str,
    *,
    cwd: Path | None = None,
    intersect_with: frozenset[str] | None = None,
    runner: object = None,
) -> DiffSelection:
    """High-level helper used by the CLI.

    Resolves the diff, computes impacted modules, and optionally
    intersects with an already-specified module set (``--modules``).
    """

    changed = changed_files_against(base_ref, cwd=cwd, runner=runner)
    selection = impacted_modules(changed)
    if intersect_with is not None:
        return DiffSelection(
            modules=selection.modules & intersect_with,
            changed_files=selection.changed_files,
            all_invalidated=selection.all_invalidated,
        )
    return selection


__all__ = [
    "ALL_MODULES",
    "DiffSelection",
    "GitNotAvailableError",
    "changed_files_against",
    "impacted_modules",
    "select_modules",
]
