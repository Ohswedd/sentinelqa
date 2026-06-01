"""Draft a Keep a Changelog section from Conventional Commits in ``git log``.

Pure-stdlib so contributors don't need ``git-cliff`` installed locally; this is
also the canonical drafter exercised by
``tests/integration/release/test_changelog_drafting.py``.

Usage
-----.. code-block:: bash

 # Default: HEAD back to the last tag (or repo root if no tag), Unreleased section.
 python -m scripts.release.draft_changelog -o CHANGELOG.draft.md

 # Pin a specific range and version header.
 python -m scripts.release.draft_changelog \
 --from v0.6.0 --to HEAD --version 0.7.0 --date 2026-06-01 \
 -o CHANGELOG.draft.md

 # Include the "Internal" bucket (chore/ci/docs/test/build/style).
 python -m scripts.release.draft_changelog --include-internal -o CHANGELOG.draft.md

The drafter is intentionally conservative:

* Strict Conventional Commits (``type(scope)?: summary`` or ``type!: summary``)
 are recognised.
* ``later: …`` and ``later: …`` (legacy phase-merge titles used pre-)
 are recognised and classified as ``feat`` with scope ``phase-NN``.
* Everything else is dropped silently — drafts never invent entries.

It is NOT the canonical CHANGELOG; ``CHANGELOG.md`` is hand-curated from these
drafts (see ``docs/dev/semver.md`` and the pre-1.0 review checklist).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Conventional Commits → Keep a Changelog mapping
# --------------------------------------------------------------------------- #

# Order matters — render preserves Keep-a-Changelog's section order.
CHANGELOG_ORDER: tuple[str, ...] = (
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
)

INTERNAL_CATEGORY = "Internal"

TYPE_TO_CATEGORY: dict[str, str] = {
    "feat": "Added",
    "fix": "Fixed",
    "security": "Security",
    "refactor": "Changed",
    "perf": "Changed",
    "revert": "Changed",
}

INTERNAL_TYPES: frozenset[str] = frozenset({"chore", "ci", "build", "test", "docs", "style"})

_SUBJECT_RE = re.compile(
    r"^(?P<type>[a-z]+)" r"(?:\((?P<scope>[^)]+)\))?" r"(?P<breaking>!)?" r": (?P<summary>.+)$"
)
_PHASE_RE = re.compile(r"^[Pp]hase\s+(?P<num>\d+):\s*(?P<summary>.+)$")


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Commit:
    """A single Conventional Commits entry plus its Keep-a-Changelog bucket."""

    sha: str
    type: str
    scope: str | None
    breaking: bool
    summary: str
    category: str  # one of CHANGELOG_ORDER or INTERNAL_CATEGORY


def parse_subject(sha: str, subject: str) -> Commit | None:
    """Parse a single commit subject. Returns ``None`` if the subject doesn't
    match a recognised pattern."""
    s = subject.strip()
    m = _SUBJECT_RE.match(s)
    if m:
        ctype = m.group("type")
        breaking = bool(m.group("breaking"))
        if breaking:
            category = "Changed"
        elif ctype in TYPE_TO_CATEGORY:
            category = TYPE_TO_CATEGORY[ctype]
        elif ctype in INTERNAL_TYPES:
            category = INTERNAL_CATEGORY
        else:
            return None
        return Commit(
            sha=sha,
            type=ctype,
            scope=m.group("scope"),
            breaking=breaking,
            summary=m.group("summary").strip(),
            category=category,
        )
    m2 = _PHASE_RE.match(s)
    if m2:
        num = int(m2.group("num"))
        return Commit(
            sha=sha,
            type="feat",
            scope=f"phase-{num:02d}",
            breaking=False,
            summary=m2.group("summary").strip(),
            category="Added",
        )
    return None


def parse_log(lines: Iterable[str]) -> list[Commit]:
    """Parse output of ``git log --no-merges --format=%H%x09%s``."""
    out: list[Commit] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line or "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        parsed = parse_subject(sha, subject)
        if parsed is not None:
            out.append(parsed)
    return out


# --------------------------------------------------------------------------- #
# Grouping + rendering
# --------------------------------------------------------------------------- #


def group_commits(
    commits: Sequence[Commit], *, include_internal: bool = False
) -> dict[str, list[Commit]]:
    order = list(CHANGELOG_ORDER)
    if include_internal:
        order.append(INTERNAL_CATEGORY)
    groups: dict[str, list[Commit]] = {k: [] for k in order}
    for c in commits:
        if c.category in groups:
            groups[c.category].append(c)
    return groups


def render_entry(c: Commit) -> str:
    scope = f"**{c.scope}**: " if c.scope else ""
    breaking = "**BREAKING** " if c.breaking else ""
    return f"- {breaking}{scope}{c.summary} ({c.sha[:7]})"


def render_section(groups: dict[str, list[Commit]], *, version: str, date: str) -> str:
    header = f"## [{version}]"
    if date:
        header += f" - {date}"
    lines: list[str] = [header, ""]
    wrote_any = False
    for cat, entries in groups.items():
        if not entries:
            continue
        wrote_any = True
        lines.append(f"### {cat}")
        for c in entries:
            lines.append(render_entry(c))
        lines.append("")
    if not wrote_any:
        lines.append("_No user-visible changes in this range._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Git wiring
# --------------------------------------------------------------------------- #


def git_log_subjects(
    from_rev: str | None,
    to_rev: str,
    *,
    cwd: str | None = None,
) -> list[str]:
    """Return ``%H<TAB>%s`` lines for the requested revision range."""
    spec = f"{from_rev}..{to_rev}" if from_rev else to_rev
    result = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x09%s", spec],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def draft(
    *,
    from_rev: str | None = None,
    to_rev: str = "HEAD",
    version: str = "Unreleased",
    date: str = "",
    include_internal: bool = False,
    cwd: str | None = None,
) -> str:
    subjects = git_log_subjects(from_rev, to_rev, cwd=cwd)
    commits = parse_log(subjects)
    groups = group_commits(commits, include_internal=include_internal)
    return render_section(groups, version=version, date=date)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="draft_changelog",
        description=("Draft a Keep a Changelog section from Conventional Commits."),
    )
    p.add_argument(
        "--from",
        dest="from_rev",
        default=None,
        help="Lower bound (exclusive). Default: repo root.",
    )
    p.add_argument(
        "--to",
        dest="to_rev",
        default="HEAD",
        help="Upper bound (inclusive). Default: HEAD.",
    )
    p.add_argument(
        "--version",
        default="Unreleased",
        help='Version header. Default: "Unreleased".',
    )
    p.add_argument(
        "--date",
        default="",
        help='ISO date for the version header. Omit for "Unreleased".',
    )
    p.add_argument(
        "--include-internal",
        action="store_true",
        help="Include chore / ci / docs / test / build / style commits.",
    )
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to write. Default: stdout.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        text = draft(
            from_rev=args.from_rev,
            to_rev=args.to_rev,
            version=args.version,
            date=args.date,
            include_internal=args.include_internal,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(
            "git log failed:\n" f"  command: {' '.join(exc.cmd)}\n" f"  stderr: {exc.stderr}\n"
        )
        return 2
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
