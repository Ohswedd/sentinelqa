"""Deterministic shard splitting + per-shard result merge (Phase 08.03).

Sharding is by **test file** (Playwright's own shard semantics work the
same way), keyed on a stable hash of the spec path. Two runs of
``sentinel test --shard 1/N`` then ``--shard 2/N`` … ``--shard N/N``
together cover exactly the set the unsharded run would have executed —
no overlap, no gaps — and the union of their results, after
:func:`merge_outcomes`, matches the single-shard outcome modulo per-test
ordering.

The hash is :func:`hashlib.sha1` (NOT Python's randomized ``hash()``) so
the same shard split is reproducible across processes, machines, and
Python versions (CLAUDE.md §19 — deterministic outputs).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
)


@dataclass(frozen=True)
class ShardSpec:
    """A single shard: ``current`` of ``total`` (both 1-indexed)."""

    current: int
    total: int

    def __post_init__(self) -> None:
        if self.current < 1 or self.total < 1:
            raise ValueError(f"shard indices must be ≥ 1 (got {self.current}/{self.total}).")
        if self.current > self.total:
            raise ValueError(f"shard {self.current}/{self.total}: current must be ≤ total.")

    @classmethod
    def parse(cls, value: str) -> ShardSpec:
        """Parse the ``"N/M"`` string form from config / CLI."""

        try:
            current_s, total_s = value.split("/", 1)
            return cls(current=int(current_s), total=int(total_s))
        except ValueError as exc:
            raise ValueError(f"shard spec must be of the form 'N/M' (got {value!r}).") from exc

    def __str__(self) -> str:  # pragma: no cover — trivial
        return f"{self.current}/{self.total}"


def _hash_to_index(path: str, total: int) -> int:
    """Map ``path`` to a stable shard index in ``[0, total)``."""

    digest = hashlib.sha1(path.encode("utf-8"), usedforsecurity=False).digest()
    # First 8 bytes is plenty (entropy ≫ 64-bit shard ceilings).
    value = int.from_bytes(digest[:8], "big")
    return value % total


def split_shard(
    spec_files: Sequence[str | Path],
    shard: ShardSpec,
) -> list[str]:
    """Return the subset of ``spec_files`` assigned to ``shard``.

    Files are returned in lexicographic order (stable across shards and
    machines) using POSIX-style separators so Windows / macOS / Linux
    agree on the hash.
    """

    normalized: list[str] = sorted(Path(p).as_posix() for p in spec_files)
    target = shard.current - 1  # 0-indexed shard index
    out: list[str] = []
    for path in normalized:
        if _hash_to_index(path, shard.total) == target:
            out.append(path)
    return out


def merge_outcomes(
    outcomes: Iterable[RunnerOutcome],
    *,
    module_name: str,
) -> RunnerOutcome:
    """Combine per-shard outcomes into a single :class:`RunnerOutcome`.

    Test executions are deduplicated by ``test_id`` (last writer wins —
    a test that ran in shard 2 overrides any phantom record). Module
    status is the worst of the constituent statuses. ``errors`` are
    concatenated; ``environment`` is taken from the first non-None
    outcome.
    """

    outcomes_list = list(outcomes)
    if not outcomes_list:
        raise ValueError("merge_outcomes requires at least one outcome.")

    # Dedup tests by test_id, preserving last writer.
    executions_by_id: dict[str, TestExecution] = {}
    for outcome in outcomes_list:
        for execution in outcome.tests:
            executions_by_id[execution.test_id] = execution

    # Determine the merged status: any "failed"/"errored" wins, else
    # "incomplete" if any source was incomplete, else "passed".
    statuses = {o.module_result.status for o in outcomes_list}
    if "errored" in statuses:
        merged_status = "errored"
    elif "failed" in statuses:
        merged_status = "failed"
    elif "incomplete" in statuses:
        merged_status = "incomplete"
    elif "skipped" in statuses and statuses == {"skipped"}:
        merged_status = "skipped"
    else:
        merged_status = "passed"

    # Merge errors (preserve order, dedup adjacent dupes).
    errors: list[str] = []
    for outcome in outcomes_list:
        for err in outcome.module_result.errors:
            if not errors or errors[-1] != err:
                errors.append(err)

    environment = next(
        (o.environment for o in outcomes_list if o.environment is not None),
        None,
    )

    # Merge findings (dedup by id).
    findings_by_id = {}
    for outcome in outcomes_list:
        for finding in outcome.module_result.findings:
            findings_by_id[finding.id] = finding

    sorted_executions = sorted(executions_by_id.values(), key=lambda t: t.test_id)
    duration_ms = sum(o.module_result.duration_ms for o in outcomes_list)
    return RunnerOutcome.build(
        module_name=module_name,
        module_id=outcomes_list[0].module_result.id,
        status=merged_status,  # type: ignore[arg-type]
        tests=tuple(sorted_executions),
        findings=tuple(sorted(findings_by_id.values(), key=lambda f: f.id)),
        errors=tuple(errors),
        duration_ms=duration_ms,
        environment=environment
        or EnvironmentContext(
            browser="chromium",
            browser_version="unknown",
            os=os.name,
            node_version=None,
            playwright_version=None,
        ),
        metrics_extra=None,
    )


__all__ = ["ShardSpec", "merge_outcomes", "split_shard"]
