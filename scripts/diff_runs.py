"""Determinism helper for SentinelQA run artifacts (Phase 29.03).

Given two or more ``.sentinel/runs/<id>/`` directories, walk every artifact,
strip the fields that are *expected* to differ between runs (timestamps,
durations, run IDs), and print any remaining diff.

Usage:

    uv run python -m scripts.diff_runs <run-a-dir> <run-b-dir> [<run-c-dir> ...]
    uv run python -m scripts.diff_runs --files run-a/findings.json run-b/findings.json

Exit codes:

* ``0`` — the runs are byte-equal after normalization.
* ``1`` — at least one residual diff remained (printed to stdout).
* ``2`` — the inputs were malformed (e.g. a non-existent directory).

The list of "allowed to differ" fields lives in :data:`VOLATILE_FIELDS` so
the policy is auditable. Pass ``--strict`` to disable the allowlist; useful
when you want to confirm the goldens really are byte-stable.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Fields the orchestrator legitimately re-stamps on every run.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "run_id",
        "started_at",
        "finished_at",
        "generated_at",
        "ts",
        "decided_at",
        "duration_ms",
        # Allow per-finding/timestamp variation so we can compare goldens
        # to live runs as well.
        "created_at",
        "updated_at",
    }
)

# Top-level keys we strip from `run.json` envelopes for the same reason.
VOLATILE_TOP_LEVEL: frozenset[str] = frozenset({"artifact_paths", "config_digest"})

# Lines in audit.log are JSONL; strip the volatile fields from each line.
AUDIT_LOG_NAME: str = "audit.log"

# Replace run-id substrings inside string values so e.g. an `evidence.path`
# of "runs/RUN-XYZ/traces/foo.har" doesn't read as a diff.
RUN_ID_RE: re.Pattern[str] = re.compile(r"RUN-[A-Z0-9]{12}")
RUN_ID_PLACEHOLDER: str = "RUN-XXXXXXXXXXXX"


def _normalize(value: Any, *, strict: bool) -> Any:
    """Strip volatile fields recursively.

    Strings have run-id substrings replaced unless ``strict`` is set.
    """

    if isinstance(value, dict):
        return {
            k: _normalize(v, strict=strict)
            for k, v in sorted(value.items())
            if strict or k not in VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [_normalize(v, strict=strict) for v in value]
    if isinstance(value, str):
        if strict:
            return value
        return RUN_ID_RE.sub(RUN_ID_PLACEHOLDER, value)
    return value


def _normalize_json_text(text: str, *, strict: bool, is_run_json: bool) -> str:
    payload = json.loads(text)
    if is_run_json and isinstance(payload, dict) and not strict:
        payload = {k: v for k, v in payload.items() if k not in VOLATILE_TOP_LEVEL}
    canonical = _normalize(payload, strict=strict)
    return json.dumps(canonical, indent=2, sort_keys=True)


def _normalize_audit_log(text: str, *, strict: bool) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            out.append(_normalize_string_line(raw, strict=strict))
            continue
        out.append(json.dumps(_normalize(row, strict=strict), sort_keys=True))
    return "\n".join(out)


def _normalize_string_line(text: str, *, strict: bool) -> str:
    return text if strict else RUN_ID_RE.sub(RUN_ID_PLACEHOLDER, text)


def _normalize_file(path: Path, *, strict: bool) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    name = path.name
    if name == AUDIT_LOG_NAME:
        return _normalize_audit_log(raw, strict=strict)
    if name.endswith(".json"):
        try:
            return _normalize_json_text(raw, strict=strict, is_run_json=name == "run.json")
        except json.JSONDecodeError:
            return _normalize_string_line(raw, strict=strict)
    return _normalize_string_line(raw, strict=strict)


def _file_set(directory: Path) -> set[Path]:
    return {p.relative_to(directory) for p in directory.rglob("*") if p.is_file()}


def diff_directories(dirs: list[Path], *, strict: bool) -> list[str]:
    """Return a list of human-readable diff lines (empty == clean)."""

    if len(dirs) < 2:
        raise ValueError("need at least two directories to diff")

    reference = dirs[0]
    reference_files = _file_set(reference)
    diffs: list[str] = []

    for other in dirs[1:]:
        other_files = _file_set(other)
        only_in_a = sorted(reference_files - other_files)
        only_in_b = sorted(other_files - reference_files)
        if only_in_a:
            diffs.append(f"files present in {reference} but missing in {other}:")
            for f in only_in_a:
                diffs.append(f"  - {f}")
        if only_in_b:
            diffs.append(f"files present in {other} but missing in {reference}:")
            for f in only_in_b:
                diffs.append(f"  - {f}")

        for rel in sorted(reference_files & other_files):
            a = _normalize_file(reference / rel, strict=strict)
            b = _normalize_file(other / rel, strict=strict)
            if a != b:
                diff = "\n".join(
                    difflib.unified_diff(
                        a.splitlines(),
                        b.splitlines(),
                        fromfile=str(reference / rel),
                        tofile=str(other / rel),
                        lineterm="",
                    )
                )
                diffs.append(diff)
    return diffs


def diff_files(files: list[Path], *, strict: bool) -> list[str]:
    if len(files) < 2:
        raise ValueError("need at least two files to diff")
    reference = files[0]
    diffs: list[str] = []
    for other in files[1:]:
        a = _normalize_file(reference, strict=strict)
        b = _normalize_file(other, strict=strict)
        if a != b:
            diff = "\n".join(
                difflib.unified_diff(
                    a.splitlines(),
                    b.splitlines(),
                    fromfile=str(reference),
                    tofile=str(other),
                    lineterm="",
                )
            )
            diffs.append(diff)
    return diffs


def _resolve(paths: Iterable[str]) -> list[Path]:
    return [Path(p).resolve() for p in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="diff-runs", description=__doc__)
    parser.add_argument(
        "positional",
        nargs="*",
        help="One or more run directories to compare (the first is the reference).",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Compare individual files instead of full directories.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Disable the timestamp/run-id allowlist (used to verify goldens).",
    )
    args = parser.parse_args(argv)

    if args.files:
        files = _resolve(args.files)
        for f in files:
            if not f.is_file():
                print(f"error: {f} is not a regular file", file=sys.stderr)
                return 2
        diffs = diff_files(files, strict=args.strict)
    else:
        if not args.positional:
            parser.error("supply two or more run directories, or --files")
        dirs = _resolve(args.positional)
        for d in dirs:
            if not d.is_dir():
                print(f"error: {d} is not a directory", file=sys.stderr)
                return 2
        diffs = diff_directories(dirs, strict=args.strict)

    if not diffs:
        print("clean: runs are byte-equal after normalization")
        return 0
    print("\n".join(diffs))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
