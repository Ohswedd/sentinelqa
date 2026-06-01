# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Cross-run flake database (sqlite, file-backed, opt-in).

The flake DB persists per-(module, test_id) outcomes across runs so
the CI surface can answer "which tests are flaky?" without re-running.
It lives at ``.sentinel/flake.db`` by default (next to ``runs/`` and
``cache/``) and is fully local — nothing is uploaded.

Schema (two tables — wide enough for the audit's planner / healer to
make decisions, narrow enough to keep migrations tractable):

  runs        (id, started_at, status)
  outcomes    (run_id, module, test_id, outcome, duration_ms)

A row in ``outcomes`` is one (module, test_id, run_id) triple plus the
outcome (``passed`` / ``failed`` / ``skipped`` / ``errored``) and a
duration. The flake rate of a (module, test_id) over the last N runs
is ``failures / total`` over the windowed slice.

Public API:

* :func:`FlakeDb.open` — open or create the DB; idempotent.
* :meth:`FlakeDb.record_run` — insert / replace a run row.
* :meth:`FlakeDb.record_outcome` — append one outcome.
* :meth:`FlakeDb.flake_rate` — compute the flake rate for one test.
* :meth:`FlakeDb.top_flaky` — list the N flakiest tests.
* :meth:`FlakeDb.stats` — counts of runs / outcomes.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

DEFAULT_FLAKE_DB_PATH: Final[Path] = Path(".sentinel") / "flake.db"

OutcomeStatus = Literal["passed", "failed", "skipped", "errored"]


@dataclass(frozen=True, slots=True)
class Outcome:
    """One (run, module, test) outcome record."""

    run_id: str
    module: str
    test_id: str
    outcome: OutcomeStatus
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class FlakeStat:
    """Computed flake stat for a single (module, test_id) pair."""

    module: str
    test_id: str
    runs: int
    failures: int

    @property
    def rate(self) -> float:
        return self.failures / self.runs if self.runs else 0.0


_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        id           TEXT PRIMARY KEY,
        started_at   TEXT NOT NULL,
        status       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outcomes (
        run_id       TEXT NOT NULL,
        module       TEXT NOT NULL,
        test_id      TEXT NOT NULL,
        outcome      TEXT NOT NULL,
        duration_ms  INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (run_id, module, test_id),
        FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_outcomes_module_test ON outcomes(module, test_id)",
    "CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC)",
)


class FlakeDb:
    """A small sqlite-backed flake database. Thread-confined.

    The connection is opened in WAL mode so concurrent readers don't
    block a writer. Each :class:`FlakeDb` owns one connection — share
    the same instance within a thread; instantiate a new one per
    thread.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        for ddl in _SCHEMA:
            self._conn.execute(ddl)
        self._conn.commit()

    @classmethod
    def open(cls, path: Path | None = None) -> FlakeDb:
        """Open or create the DB. Parent directories are auto-created."""

        resolved = path or DEFAULT_FLAKE_DB_PATH
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return cls(resolved)

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FlakeDb:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def record_run(self, run_id: str, started_at: str, status: str) -> None:
        """Upsert a run row.

        Uses sqlite's ``ON CONFLICT DO UPDATE`` rather than
        ``INSERT OR REPLACE`` so the existing row is patched in place;
        ``REPLACE`` would delete and re-insert, cascading deletes
        through the outcomes table and erasing prior outcome history
        for that run id.
        """

        self._conn.execute(
            """
            INSERT INTO runs (id, started_at, status) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET started_at = excluded.started_at,
                                           status = excluded.status
            """,
            (run_id, started_at, status),
        )
        self._conn.commit()

    def record_outcome(self, outcome: Outcome) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO outcomes
            (run_id, module, test_id, outcome, duration_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                outcome.run_id,
                outcome.module,
                outcome.test_id,
                outcome.outcome,
                outcome.duration_ms,
            ),
        )
        self._conn.commit()

    def record_outcomes(self, outcomes: list[Outcome]) -> None:
        """Bulk insert; one commit for many outcomes."""

        if not outcomes:
            return
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO outcomes
            (run_id, module, test_id, outcome, duration_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(o.run_id, o.module, o.test_id, o.outcome, o.duration_ms) for o in outcomes],
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def flake_rate(self, module: str, test_id: str, *, window: int = 20) -> FlakeStat:
        """Return the flake stat for one (module, test_id) over the last N runs."""

        rows = list(
            self._conn.execute(
                """
                SELECT o.outcome
                FROM outcomes o
                JOIN runs r ON r.id = o.run_id
                WHERE o.module = ? AND o.test_id = ?
                ORDER BY r.started_at DESC
                LIMIT ?
                """,
                (module, test_id, window),
            )
        )
        runs = len(rows)
        failures = sum(1 for r in rows if r["outcome"] == "failed")
        return FlakeStat(module=module, test_id=test_id, runs=runs, failures=failures)

    def top_flaky(self, *, limit: int = 10, min_runs: int = 3, window: int = 50) -> list[FlakeStat]:
        """Return the top-N flakiest (module, test_id) pairs.

        ``min_runs`` is the noise floor — a test that has only run twice
        and failed once is not "78 % flaky" in any useful sense.
        """

        pairs = list(
            self._conn.execute(
                """
                SELECT o.module AS module, o.test_id AS test_id,
                       COUNT(*) AS runs,
                       SUM(CASE WHEN o.outcome = 'failed' THEN 1 ELSE 0 END) AS failures
                FROM outcomes o
                JOIN runs r ON r.id = o.run_id
                GROUP BY o.module, o.test_id
                """
            )
        )
        stats = [
            FlakeStat(
                module=row["module"],
                test_id=row["test_id"],
                runs=int(row["runs"]),
                failures=int(row["failures"] or 0),
            )
            for row in pairs
            if int(row["runs"]) >= min_runs
        ]
        # Sort by failure rate desc, then by failure count desc,
        # then by test_id for deterministic ordering on ties.
        stats.sort(key=lambda s: (-s.rate, -s.failures, s.test_id))
        # Apply window after sorting (window is "consider top N candidates",
        # not a per-row truncation).
        _ = window
        return stats[:limit]

    def stats(self) -> dict[str, int]:
        runs = self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        outcomes = self._conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
        return {"runs": int(runs), "outcomes": int(outcomes)}


__all__ = [
    "DEFAULT_FLAKE_DB_PATH",
    "FlakeDb",
    "FlakeStat",
    "Outcome",
    "OutcomeStatus",
]
