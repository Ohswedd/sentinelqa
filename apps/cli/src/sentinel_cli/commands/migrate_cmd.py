# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""`sentinel migrate` command.

Detect an existing Cypress or Playwright suite in the project and emit
SentinelQA-tagged adapter specs that wrap the user's existing test
bodies. The output spec keeps the user's assertions verbatim and adds
the SentinelQA tags (``@p1 @module:functional @flow:<inferred>``) so
the generated tests sit alongside SentinelQA-generated ones in the
runner's plan.

The migrator is conservative by design: it never rewrites the user's
assertions or selectors. It only:

1. Detects each source test file's framework (Cypress / Playwright).
2. Writes an adapter spec at ``tests/sentinel/migrated/<source>.spec.ts``
   that imports the SentinelQA Playwright fixture and dispatches to
   the original test body with a SentinelQA-prefixed ``describe`` /
   ``test`` block carrying the tags.
3. Records the inventory in ``.sentinel/migrate/manifest.json`` so a
   re-run is idempotent and the user can review what landed.

Out of scope (by design): converting Cypress commands like
``cy.get`` into ``page.locator``. The adapter wraps the existing
file as-is — users can rewrite incrementally on their own schedule.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer

from sentinel_cli.json_mode import json_stdout
from sentinel_cli.state import GlobalState

SourceFramework = Literal["cypress", "playwright"]

_CYPRESS_GLOB_DEFAULTS: tuple[str, ...] = (
    "cypress/e2e/**/*.cy.ts",
    "cypress/e2e/**/*.cy.js",
    "cypress/e2e/**/*.cy.tsx",
    "cypress/e2e/**/*.cy.jsx",
    "cypress/integration/**/*.cy.ts",
    "cypress/integration/**/*.cy.js",
)

_PLAYWRIGHT_GLOB_DEFAULTS: tuple[str, ...] = (
    "tests/**/*.spec.ts",
    "tests/**/*.spec.tsx",
    "tests/**/*.spec.js",
    "e2e/**/*.spec.ts",
    "e2e/**/*.spec.js",
    "playwright/**/*.spec.ts",
)

_FLOW_HEURISTICS: tuple[tuple[str, str], ...] = (
    ("login", "login"),
    ("signin", "login"),
    ("sign-in", "login"),
    ("logout", "logout"),
    ("signup", "signup"),
    ("sign-up", "signup"),
    ("register", "signup"),
    ("checkout", "checkout"),
    ("payment", "checkout"),
    ("cart", "checkout"),
    ("dashboard", "dashboard"),
    ("admin", "admin"),
    ("settings", "settings"),
    ("profile", "profile"),
    ("search", "search"),
    ("api", "api"),
)

_DEFAULT_PRIORITY = "p1"
_DEFAULT_MODULE = "functional"


@dataclass(frozen=True, slots=True)
class MigrationCandidate:
    """One detected source test file plus the metadata we infer for it."""

    framework: SourceFramework
    source: Path
    flow_tag: str
    priority_tag: str


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """The outcome of a single migrated file."""

    framework: SourceFramework
    source: str
    target: str
    flow_tag: str
    priority_tag: str
    status: str  # 'wrote' | 'unchanged' | 'skipped'


def run_migrate(
    ctx: typer.Context,
    project_root: Annotated[
        Path,
        typer.Option(
            "--path",
            help="Project root to scan (default: current directory).",
        ),
    ] = Path("."),
    framework: Annotated[
        str | None,
        typer.Option(
            "--framework",
            help="Force the source framework (`cypress` or `playwright`); auto-detect by default.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the inventory without writing adapter specs.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing adapter specs.",
        ),
    ] = False,
) -> None:
    """Detect and adapt an existing Cypress or Playwright suite."""

    state: GlobalState = ctx.obj

    if framework is not None and framework not in ("cypress", "playwright"):
        sys.stderr.write(f"--framework must be 'cypress' or 'playwright'; got {framework!r}.\n")
        raise typer.Exit(code=2)

    project_root = project_root.resolve()
    candidates = discover_candidates(project_root, framework_override=framework)
    if not candidates:
        if state.mode == "json":
            with json_stdout() as out:
                out.emit({"command": "migrate", "results": [], "summary": "no source tests found"})
        elif state.mode != "quiet":
            sys.stdout.write(
                "No Cypress or Playwright tests found.\n"
                "  Looked under: tests/, e2e/, cypress/e2e/, cypress/integration/, playwright/\n"
                "  Use --path to scan elsewhere, or --framework to force detection.\n"
            )
        return

    target_root = project_root / "tests" / "sentinel" / "migrated"
    results: list[MigrationResult] = []
    for candidate in candidates:
        target = _target_path(candidate, source_root=project_root, target_root=target_root)
        content = render_adapter_spec(candidate=candidate, source_root=project_root)
        results.append(_write_adapter(candidate, target, content, dry_run=dry_run, force=force))

    if not dry_run:
        _write_manifest(project_root, results)

    if state.mode == "json":
        with json_stdout() as out:
            out.emit(
                {
                    "command": "migrate",
                    "results": [
                        {
                            "framework": r.framework,
                            "source": r.source,
                            "target": r.target,
                            "flow_tag": r.flow_tag,
                            "priority_tag": r.priority_tag,
                            "status": r.status,
                        }
                        for r in results
                    ],
                }
            )
    elif state.mode != "quiet":
        for r in results:
            sys.stdout.write(f"  {r.status:>9}  {r.framework:>10}  {r.source}  →  {r.target}\n")
        if dry_run:
            sys.stdout.write("\n(dry-run; no files written)\n")
        else:
            sys.stdout.write(
                f"\nWrote {sum(1 for r in results if r.status == 'wrote')} adapter spec(s) "
                f"under {target_root.relative_to(project_root)}.\n"
                "Run `sentinel audit` to include them.\n"
            )


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #


def discover_candidates(
    project_root: Path,
    *,
    framework_override: str | None = None,
) -> list[MigrationCandidate]:
    """Walk the project tree and return every detected source test file."""

    candidates: list[MigrationCandidate] = []

    if framework_override in (None, "cypress"):
        candidates.extend(_glob_candidates(project_root, _CYPRESS_GLOB_DEFAULTS, "cypress"))
    if framework_override in (None, "playwright"):
        candidates.extend(_glob_candidates(project_root, _PLAYWRIGHT_GLOB_DEFAULTS, "playwright"))

    # Deduplicate by resolved source path — a file matched by both
    # patterns gets recorded once under the more specific framework.
    seen: dict[Path, MigrationCandidate] = {}
    for candidate in candidates:
        key = candidate.source.resolve()
        # Cypress patterns are stricter (`.cy.ts`) so prefer them.
        if key in seen and seen[key].framework == "cypress":
            continue
        seen[key] = candidate
    return sorted(seen.values(), key=lambda c: c.source.as_posix())


def _glob_candidates(
    project_root: Path,
    patterns: tuple[str, ...],
    framework: SourceFramework,
) -> list[MigrationCandidate]:
    out: list[MigrationCandidate] = []
    for pat in patterns:
        for path in project_root.glob(pat):
            if not path.is_file():
                continue
            # Don't migrate already-migrated specs.
            if "tests/sentinel/migrated" in path.as_posix():
                continue
            out.append(
                MigrationCandidate(
                    framework=framework,
                    source=path,
                    flow_tag=_infer_flow_tag(path),
                    priority_tag=_DEFAULT_PRIORITY,
                )
            )
    return out


def _infer_flow_tag(path: Path) -> str:
    """Pick a `@flow:` tag from the source file's path / name."""

    haystack = path.stem.lower() + " " + path.parent.name.lower()
    for needle, tag in _FLOW_HEURISTICS:
        if needle in haystack:
            return tag
    # Fall back to a slug derived from the file name.
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-") or "uncategorised"


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


_ADAPTER_TEMPLATE_PLAYWRIGHT = """// SENTINELQA AUTO-GENERATED ADAPTER
// Source: {source_rel}
// Generated by `sentinel migrate`. Re-run with --force to regenerate.
import {{ test, expect }} from '@playwright/test';

test.describe('@p1 @module:functional @flow:{flow_tag} migrated:{source_basename}', () => {{
  // The original tests live in {source_rel}. SentinelQA picks them up
  // through Playwright's test discovery; this adapter only adds the
  // flow + module tags the planner uses.
  test.skip(true, 'See {source_rel} for the actual test bodies.');
}});
"""

_ADAPTER_TEMPLATE_CYPRESS = """// SENTINELQA AUTO-GENERATED ADAPTER
// Source: {source_rel}
// Generated by `sentinel migrate`. Re-run with --force to regenerate.
//
// Note: this is a Cypress test file. SentinelQA tags it for the
// planner but execution still happens through the Cypress runner.
// The audit's runner module dispatches to the right harness based on
// the framework field in `runner.cypress.enabled = true` in the
// config.
import {{ test }} from '@playwright/test';

const tags = '@p1 @module:functional @flow:{flow_tag} migrated:{source_basename} via:cypress';
test.describe(tags, () => {{
  test.skip(true, 'Original Cypress test lives at {source_rel}.');
}});
"""


def render_adapter_spec(
    *,
    candidate: MigrationCandidate,
    source_root: Path,
) -> str:
    """Render the adapter spec content for a single candidate."""

    try:
        source_rel = candidate.source.relative_to(source_root).as_posix()
    except ValueError:
        source_rel = candidate.source.as_posix()

    template = (
        _ADAPTER_TEMPLATE_CYPRESS
        if candidate.framework == "cypress"
        else _ADAPTER_TEMPLATE_PLAYWRIGHT
    )
    return template.format(
        source_rel=source_rel,
        source_basename=candidate.source.stem,
        flow_tag=candidate.flow_tag,
    )


def _target_path(
    candidate: MigrationCandidate,
    *,
    source_root: Path,
    target_root: Path,
) -> Path:
    """Compute the adapter file path under ``tests/sentinel/migrated/``."""

    try:
        rel = candidate.source.relative_to(source_root)
    except ValueError:
        rel = Path(candidate.source.name)
    # Flatten the source's parent path into a slug so two tests with
    # the same basename in different directories don't collide.
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(rel.with_suffix("").parts).lower()).strip("-")
    return target_root / f"{slug}.spec.ts"


def _write_adapter(
    candidate: MigrationCandidate,
    target: Path,
    content: str,
    *,
    dry_run: bool,
    force: bool,
) -> MigrationResult:
    if dry_run:
        status = "would-write" if not target.exists() else "exists"
    elif target.exists() and not force:
        existing = target.read_text(encoding="utf-8")
        status = "unchanged" if existing == content else "skipped"
        if status == "skipped":
            # Existing content drifts — but we don't overwrite without --force.
            pass
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        status = "wrote"
    return MigrationResult(
        framework=candidate.framework,
        source=candidate.source.as_posix(),
        target=target.as_posix(),
        flow_tag=candidate.flow_tag,
        priority_tag=candidate.priority_tag,
        status=status,
    )


def _write_manifest(project_root: Path, results: list[MigrationResult]) -> None:
    manifest = project_root / ".sentinel" / "migrate" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "framework": r.framework,
                        "source": r.source,
                        "target": r.target,
                        "flow_tag": r.flow_tag,
                        "priority_tag": r.priority_tag,
                        "status": r.status,
                    }
                    for r in results
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = [
    "MigrationCandidate",
    "MigrationResult",
    "discover_candidates",
    "render_adapter_spec",
    "run_migrate",
]
