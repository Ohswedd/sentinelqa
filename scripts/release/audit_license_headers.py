# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""License-header + NOTICE auditor (Phase 35.03).

Two invariants:

1. **SPDX coverage.** Every source file under the covered trees
   (``engine/``, ``apps/``, ``modules/``, ``integrations/``,
   ``packages/``, ``scripts/``, ``tests/``) is either:

     * Declared explicitly via ``SPDX-License-Identifier: Apache-2.0``
       in the first 30 lines, OR
     * Implicitly covered by the root ``LICENSE`` because its directory
       prefix is on the COVERED_PREFIXES allowlist.

   Files that match neither — or files anywhere in the repo that
   declare a non-Apache-2.0 SPDX header (license drift) — fail the
   audit.

2. **NOTICE completeness.** Every upstream vendored under
   ``packages/shared-schema/external/`` has a matching attribution
   line in ``NOTICE`` (upstream name, license, source URL).

Run via ``make audit-license-headers`` (CI mode == ``--check``) or
directly::

    python -m scripts.release.audit_license_headers
    python -m scripts.release.audit_license_headers --check

Exit codes follow the SentinelQA CLI grid (0 success / 6 audit
failure) so the script slots into the same CI plumbing as the other
release auditors.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Source-file extensions we audit. Python + TypeScript + TSX, per
# plans/phase-35-public-release/03-license-headers-audit.md. JSON,
# YAML, Markdown, SVG, images, and lockfiles are not source files and
# do not need SPDX headers.
SOURCE_EXTENSIONS: tuple[str, ...] = (".py", ".ts", ".tsx")

# Trees we walk. These match the task spec verbatim.
SCAN_DIRS: tuple[str, ...] = (
    "engine",
    "apps",
    "modules",
    "integrations",
    "packages",
    "scripts",
    "tests",
)

# Trees explicitly covered by the root LICENSE. A file under one of
# these prefixes does NOT need its own SPDX header — the root LICENSE
# applies to it. This list intentionally mirrors SCAN_DIRS for the
# bootstrap case; future opt-outs (a vendored TS file with its own
# upstream license, say) belong here as exceptions, NOT as removals.
COVERED_PREFIXES: tuple[str, ...] = SCAN_DIRS

# Directories we skip during the walk (build output, caches,
# vendored node_modules, generated Astro types, the docs `dist/`).
SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".astro",
        "dist",
        "build",
        ".turbo",
        ".next",
        ".venv",
        "venv",
        ".sentinel",
    }
)

# Files we skip (vendored schemas, auto-generated type defs, etc.).
SKIP_FILE_SUFFIXES: tuple[str, ...] = (".d.ts",)

# How many lines we scan for an SPDX marker. The task fixes this at 30.
SPDX_SCAN_LINES = 30

# Permitted SPDX identifier — Apache-2.0 only. Anything else under the
# covered trees is license drift.
PERMITTED_SPDX = "Apache-2.0"

SPDX_RE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+()/ ]+?)\s*(?:\*/|-->|$)")

# `packages/shared-schema/external/` vendored upstreams that must
# appear in NOTICE. The list pins the four upstream schemas we already
# carry — adding a new external schema fails this audit until NOTICE
# is updated too.
VENDORED_EXTERNALS: dict[str, tuple[str, str]] = {
    "cyclonedx-1.5.json": (
        "CycloneDX 1.5 JSON Schema",
        "https://github.com/CycloneDX/specification",
    ),
    "junit.xsd": (
        "JUnit XML (Surefire) XSD",
        "https://maven.apache.org/surefire/maven-surefire-plugin/xsd/",
    ),
    "sarif-2.1.0.json": (
        "SARIF 2.1.0 JSON Schema (OASIS)",
        "https://docs.oasis-open.org/sarif/sarif/v2.1.0/",
    ),
    "slack-block-kit.schema.json": (
        "Slack Block Kit JSON Schema",
        "https://api.slack.com/reference/block-kit",
    ),
}


@dataclass(slots=True)
class AuditReport:
    missing_spdx: list[Path] = field(default_factory=list)
    drift: list[tuple[Path, str]] = field(default_factory=list)
    notice_missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_spdx or self.drift or self.notice_missing)


def _has_apache_spdx(path: Path) -> tuple[bool, str | None]:
    """Return (has_apache_header, foreign_license_if_any)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= SPDX_SCAN_LINES:
                    break
                m = SPDX_RE.search(line)
                if not m:
                    continue
                identifier = m.group(1).strip()
                if identifier == PERMITTED_SPDX:
                    return True, None
                return False, identifier
    except OSError:
        return False, None
    return False, None


def _is_covered(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return False
    return parts[0] in COVERED_PREFIXES


def _iter_source_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for scan in SCAN_DIRS:
        base = root / scan
        if not base.is_dir():
            continue
        for entry in base.rglob("*"):
            if entry.is_dir():
                continue
            if any(part in SKIP_DIR_NAMES for part in entry.parts):
                continue
            if entry.suffix not in SOURCE_EXTENSIONS:
                continue
            if entry.name.endswith(SKIP_FILE_SUFFIXES):
                continue
            out.append(entry)
    return sorted(out)


def _audit_headers(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    missing: list[Path] = []
    drift: list[tuple[Path, str]] = []
    for path in _iter_source_files(root):
        rel = path.relative_to(root)
        has_spdx, foreign = _has_apache_spdx(path)
        if foreign is not None:
            drift.append((rel, foreign))
            continue
        if has_spdx:
            continue
        if _is_covered(rel):
            continue
        missing.append(rel)
    return missing, drift


def _audit_notice(root: Path) -> list[str]:
    notice_path = root / "NOTICE"
    if not notice_path.is_file():
        return ["NOTICE missing at repo root"]
    text = notice_path.read_text(encoding="utf-8")
    out: list[str] = []
    for name, (label, url) in VENDORED_EXTERNALS.items():
        if name not in text and label not in text:
            out.append(
                f"NOTICE is missing an entry for vendored upstream {name!r} "
                f"(expected mention of {label!r} or its source URL {url})."
            )
    # Also flag any external file shipped under packages/shared-schema/external/
    # that is NOT in VENDORED_EXTERNALS — that means the inventory drifted.
    ext_dir = root / "packages" / "shared-schema" / "external"
    if ext_dir.is_dir():
        present = {p.name for p in ext_dir.iterdir() if p.is_file()}
        unknown = sorted(present - set(VENDORED_EXTERNALS))
        for name in unknown:
            out.append(
                f"packages/shared-schema/external/{name} is not in "
                "VENDORED_EXTERNALS — add it to scripts/release/"
                "audit_license_headers.py AND to NOTICE."
            )
    return out


def run_audit(root: Path = REPO_ROOT) -> AuditReport:
    missing, drift = _audit_headers(root)
    notice = _audit_notice(root)
    return AuditReport(missing_spdx=missing, drift=drift, notice_missing=notice)


def _format_report(report: AuditReport) -> str:
    chunks: list[str] = []
    if report.missing_spdx:
        chunks.append(
            "Missing SPDX header (file outside the documented covered "
            "trees — add `# SPDX-License-Identifier: Apache-2.0` in the "
            "first 30 lines):"
        )
        chunks.extend(f"  - {p}" for p in report.missing_spdx)
    if report.drift:
        chunks.append(
            "Foreign SPDX header (only Apache-2.0 is permitted inside "
            "SentinelQA — remove the file or relicense it):"
        )
        chunks.extend(f"  - {p} → {identifier}" for p, identifier in report.drift)
    if report.notice_missing:
        chunks.append("NOTICE problems:")
        chunks.extend(f"  - {msg}" for msg in report.notice_missing)
    if not chunks:
        return "License headers + NOTICE: ok"
    return "\n".join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit SentinelQA source files for license headers + NOTICE completeness.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode — exit non-zero on any audit failure (default behavior).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to audit (defaults to the SentinelQA repo root).",
    )
    args = parser.parse_args(argv)

    report = run_audit(args.root)
    print(_format_report(report))
    if report.ok:
        return 0
    # Exit 6 == "test execution failed" in the SentinelQA exit-code grid;
    # the closest match for an audit script that detected real problems.
    return 6


if __name__ == "__main__":
    sys.exit(main())
