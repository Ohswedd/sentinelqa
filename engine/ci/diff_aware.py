"""Diff-aware test selection (the documentation, §12.3, task 17.05).

Translates a git diff range into a set of impacted routes, API
endpoints, and test files. Falls back to full-mode selection when the
diff is large or touches a high-blast-radius file (lockfile, framework
config, Dockerfile).

The translation is deterministic and pure: :func:`select_from_files`
takes the changed-file list and a small policy. :func:`select_from_git`
is a thin wrapper around ``git diff --name-only`` for the CLI path.
The Phase 17 ``sentinel ci --diff`` command merges the returned
:class:`DiffSelection` into the lifecycle ``module_options`` channel.

Implementation discipline:

- Always include the smoke (`@p0`) tag set, regardless of what changed
  (our engineering rules — smoke is the floor).
- Path heuristics are deliberately narrow and match the major React /
  Next.js / Vite layouts; unknown projects fall back to full mode
  rather than guessing.
- Subprocess invocation uses :mod:`subprocess` with ``shell=False`` and
  argument vectors only (our engineering rules — no shell-string injection).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

DEFAULT_MAX_CHANGED_FILES: Final[int] = 50
"""Above this count the diff is treated as broad → fall back to full mode."""

SMOKE_TAG: Final[str] = "@p0"
"""The mandatory smoke tag every PR runs."""

# ---------------------------------------------------------------------------
# Heuristic catalogues
# ---------------------------------------------------------------------------

# Route file patterns. Tested in document order; the first match wins.
_ROUTE_PATTERNS: Final[tuple[tuple[re.Pattern[str], int], ...]] = (
    # Next.js App Router (app/<path>/page.tsx)
    (re.compile(r"^app/(?P<path>.+)/page\.(?:tsx|jsx|ts|js)$"), 1),
    # Next.js App Router root page (app/page.tsx)
    (re.compile(r"^app/page\.(?:tsx|jsx|ts|js)$"), 0),
    # Next.js Pages Router (pages/foo/bar.tsx)
    (re.compile(r"^pages/(?P<path>.+)\.(?:tsx|jsx|ts|js)$"), 1),
    # Vite + React Router (src/routes/foo.tsx)
    (re.compile(r"^src/routes/(?P<path>.+)\.(?:tsx|jsx|ts|js)$"), 1),
    # Vite-style src/pages/
    (re.compile(r"^src/pages/(?P<path>.+)\.(?:tsx|jsx|ts|js)$"), 1),
)

# API endpoint patterns. Sequence and match semantics mirror route patterns.
_API_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^app/api/(?P<path>.+)/route\.(?:tsx|jsx|ts|js)$"),
    re.compile(r"^pages/api/(?P<path>.+)\.(?:tsx|jsx|ts|js)$"),
    re.compile(r"^api/(?P<path>.+)\.(?:tsx|jsx|ts|js|py)$"),
)

# OpenAPI / GraphQL schema files — any change → all API tests impacted.
_OPENAPI_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?:^|/)openapi\.(?:yaml|yml|json)$"),
    re.compile(r"(?:^|/)openapi/.+\.(?:yaml|yml|json)$"),
    re.compile(r"(?:^|/)schema\.graphql$"),
    re.compile(r"(?:^|/)graphql\.schema$"),
)

# High-blast-radius files — any change forces fallback to full mode.
_BROAD_IMPACT_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
        "uv.lock",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "Pipfile.lock",
        "Dockerfile",
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "vite.config.ts",
        "vite.config.js",
        "tsconfig.json",
        "tsconfig.base.json",
        "tailwind.config.js",
        "tailwind.config.ts",
        "postcss.config.js",
        "babel.config.js",
        "vitest.config.ts",
        "vitest.config.js",
        "playwright.config.ts",
        "playwright.config.js",
        "remix.config.js",
    }
)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffSelection:
    """The resolved selection for a single ``sentinel ci --diff`` run.

    The CLI consumes :attr:`grep` (which merges with the mode preset)
    and :attr:`fallback_to_full`. Other fields are surfaced through
    ``ci.json`` so the PR comment / HTML report can show "we audited X
    because Y changed".
    """

    diff_range: str
    changed_files: tuple[str, ...]
    impacted_routes: tuple[str, ...] = field(default_factory=tuple)
    impacted_endpoints: tuple[str, ...] = field(default_factory=tuple)
    impacted_test_files: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    fallback_to_full: bool = False
    reason: str = ""

    def grep(self) -> str | None:
        """Return the Playwright ``--grep`` filter for this selection.

        - Full-mode fallback → no filter.
        - Otherwise, always include the smoke tag set so P0 runs.
        """

        if self.fallback_to_full:
            return None
        tag_set = set(self.tags)
        tag_set.add(SMOKE_TAG)
        return "|".join(sorted(tag_set))

    def to_dict(self) -> dict[str, object]:
        return {
            "diff_range": self.diff_range,
            "changed_files": list(self.changed_files),
            "impacted_routes": list(self.impacted_routes),
            "impacted_endpoints": list(self.impacted_endpoints),
            "impacted_test_files": list(self.impacted_test_files),
            "tags": list(self.tags),
            "fallback_to_full": self.fallback_to_full,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Pure entry points
# ---------------------------------------------------------------------------


def select_from_files(
    *,
    diff_range: str,
    changed_files: Sequence[str],
    max_changed_files: int = DEFAULT_MAX_CHANGED_FILES,
) -> DiffSelection:
    """Translate the changed-file list into a deterministic selection.

    No filesystem or git access — pass the list of POSIX file paths
    relative to the repository root.
    """

    normalized = tuple(_normalize(path) for path in changed_files if path)
    deduped = tuple(dict.fromkeys(normalized))

    # Broad-impact tripwire (lockfile / framework config / Dockerfile).
    broad_hits = [path for path in deduped if _is_broad_impact(path)]
    if broad_hits:
        return DiffSelection(
            diff_range=diff_range,
            changed_files=deduped,
            fallback_to_full=True,
            reason=(f"broad-impact file changed ({broad_hits[0]}); " "running full regression."),
        )

    # Volume tripwire — too many files to safely subset.
    if len(deduped) > max_changed_files:
        return DiffSelection(
            diff_range=diff_range,
            changed_files=deduped,
            fallback_to_full=True,
            reason=(
                f"{len(deduped)} files changed (> {max_changed_files} threshold); "
                "running full regression."
            ),
        )

    routes: list[str] = []
    endpoints: list[str] = []
    impacted_specs: list[str] = []
    openapi_changed = False
    test_files = [p for p in deduped if _is_test_file(p)]
    impacted_specs.extend(test_files)

    for path in deduped:
        if _matches_any(_OPENAPI_PATTERNS, path):
            openapi_changed = True
            continue
        route = _route_for_file(path)
        if route is not None:
            routes.append(route)
        endpoint = _endpoint_for_file(path)
        if endpoint is not None:
            endpoints.append(endpoint)

    # Deduplicate while keeping deterministic alphabetical order.
    impacted_routes = tuple(sorted(set(routes)))
    impacted_endpoints = tuple(sorted(set(endpoints)))
    impacted_test_files = tuple(sorted(set(impacted_specs)))

    tags: list[str] = []
    if impacted_routes or impacted_endpoints or impacted_specs or openapi_changed:
        # P0 + P1 covers smoke and "required gates". Diff-aware never
        # drops below P0 (the SMOKE_TAG floor is enforced in ``grep()``).
        tags.append("@p1")
    if openapi_changed:
        # All API tests are impacted when the schema changes.
        tags.append("@module:api")
    for route in impacted_routes:
        tags.append(f"@route:{route}")
    for endpoint in impacted_endpoints:
        tags.append(f"@endpoint:{endpoint}")

    return DiffSelection(
        diff_range=diff_range,
        changed_files=deduped,
        impacted_routes=impacted_routes,
        impacted_endpoints=impacted_endpoints,
        impacted_test_files=impacted_test_files,
        tags=tuple(dict.fromkeys(tags)),
        fallback_to_full=False,
        reason=(
            f"{len(deduped)} file(s) changed; mapped to "
            f"{len(impacted_routes)} route(s) + "
            f"{len(impacted_endpoints)} endpoint(s)."
        ),
    )


def select_from_git(
    *,
    diff_range: str,
    repo_root: Path,
    max_changed_files: int = DEFAULT_MAX_CHANGED_FILES,
    runner: callable | None = None,  # type: ignore[type-arg]
) -> DiffSelection:
    """Read the changed file set from ``git`` and translate to a selection.

    ``runner`` is an injection point for tests — the default invokes
    ``git diff --name-only <range>`` via :mod:`subprocess`.
    """

    cmd_runner = runner or _default_git_runner
    files = cmd_runner(diff_range=diff_range, repo_root=repo_root)
    return select_from_files(
        diff_range=diff_range,
        changed_files=files,
        max_changed_files=max_changed_files,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _default_git_runner(
    *,
    diff_range: str,
    repo_root: Path,
) -> tuple[str, ...]:
    """Invoke ``git diff --name-only <range>`` and return POSIX paths."""

    git_bin = shutil.which("git")
    if git_bin is None:
        # The CLI surfaces a typed DependencyMissingError; here we just
        # raise FileNotFoundError so callers can convert as they wish.
        raise FileNotFoundError("git not on PATH; cannot resolve --diff range.")

    try:
        result = subprocess.run(
            [git_bin, "diff", "--name-only", diff_range],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"git diff --name-only {diff_range!r} failed: {exc.stderr.strip()}"
        ) from exc

    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _normalize(path: str) -> str:
    # Normalize backslashes to POSIX so Windows checkouts behave.
    return path.replace("\\", "/").lstrip("./")


def _is_broad_impact(path: str) -> bool:
    basename = path.rsplit("/", 1)[-1]
    return basename in _BROAD_IMPACT_FILENAMES


def _is_test_file(path: str) -> bool:
    if "tests/sentinel/" in path:
        return True
    return path.endswith((".spec.ts", ".spec.tsx", ".spec.js", ".test.ts", ".test.tsx"))


def _matches_any(patterns: Iterable[re.Pattern[str]], path: str) -> bool:
    return any(pat.search(path) for pat in patterns)


def _route_for_file(path: str) -> str | None:
    for pattern, group_count in _ROUTE_PATTERNS:
        match = pattern.match(path)
        if match is None:
            continue
        if group_count == 0:
            return "/"
        raw = match.group("path")
        return "/" + _strip_index(raw)
    return None


def _endpoint_for_file(path: str) -> str | None:
    for pattern in _API_PATTERNS:
        match = pattern.match(path)
        if match is None:
            continue
        raw = match.group("path")
        return "/api/" + _strip_index(raw)
    return None


def _strip_index(raw: str) -> str:
    if raw.endswith("/index"):
        return raw[: -len("/index")]
    if raw == "index":
        return ""
    return raw


__all__ = [
    "DEFAULT_MAX_CHANGED_FILES",
    "DiffSelection",
    "SMOKE_TAG",
    "select_from_files",
    "select_from_git",
]
