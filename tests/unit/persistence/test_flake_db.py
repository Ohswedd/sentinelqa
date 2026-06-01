# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the cross-run flake database."""

from __future__ import annotations

from pathlib import Path

from engine.persistence.flake_db import FlakeDb, Outcome


def _populate(db: FlakeDb, *, runs: int, module: str, test_id: str, fail_every: int) -> None:
    """Create ``runs`` rows; fail this test every ``fail_every``-th run."""

    for i in range(runs):
        run_id = f"RUN-XXXXXXXX{i:04d}"
        db.record_run(run_id, started_at=f"2026-06-01T00:{i:02d}:00+00:00", status="passed")
        outcome = "failed" if i % fail_every == 0 else "passed"
        db.record_outcome(Outcome(run_id=run_id, module=module, test_id=test_id, outcome=outcome))


def test_open_creates_db_and_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "flake.db"
    db = FlakeDb.open(db_path)
    try:
        assert db_path.is_file()
        stats = db.stats()
        assert stats == {"runs": 0, "outcomes": 0}
    finally:
        db.close()


def test_record_run_then_outcome_round_trips(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        db.record_run("RUN-XAAAAAAAAAAA", started_at="2026-06-01T00:00:00+00:00", status="passed")
        db.record_outcome(
            Outcome(
                run_id="RUN-XAAAAAAAAAAA",
                module="functional",
                test_id="login-flow",
                outcome="failed",
                duration_ms=1234,
            )
        )
        stat = db.flake_rate("functional", "login-flow")
        assert stat.runs == 1
        assert stat.failures == 1
        assert stat.rate == 1.0
    finally:
        db.close()


def test_flake_rate_over_window(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        _populate(db, runs=20, module="functional", test_id="t1", fail_every=4)
        stat = db.flake_rate("functional", "t1", window=20)
        # 5 failures (i = 0, 4, 8, 12, 16) of 20 runs = 25%.
        assert stat.runs == 20
        assert stat.failures == 5
        assert stat.rate == 0.25
    finally:
        db.close()


def test_top_flaky_excludes_low_run_counts(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        # 50 runs of "t1" with 25% flake rate.
        _populate(db, runs=50, module="m", test_id="t1", fail_every=4)
        # 2 runs of "t2" with 100% flake — under the floor.
        _populate(db, runs=2, module="m", test_id="t2", fail_every=1)
        result = db.top_flaky(min_runs=3)
        ids = [s.test_id for s in result]
        assert "t1" in ids
        assert "t2" not in ids
    finally:
        db.close()


def test_top_flaky_sorts_by_rate_then_failures(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        _populate(db, runs=10, module="m", test_id="t-low", fail_every=10)  # 10% rate
        _populate(db, runs=10, module="m", test_id="t-high", fail_every=2)  # 50% rate
        _populate(db, runs=10, module="m", test_id="t-mid", fail_every=4)  # 30% rate
        result = db.top_flaky()
        ordering = [s.test_id for s in result]
        assert ordering[0] == "t-high"
        assert ordering[1] == "t-mid"
        assert ordering[2] == "t-low"
    finally:
        db.close()


def test_top_flaky_respects_limit(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        for i in range(15):
            _populate(db, runs=5, module="m", test_id=f"t{i}", fail_every=2)
        result = db.top_flaky(limit=5)
        assert len(result) == 5
    finally:
        db.close()


def test_record_outcomes_bulk_writes(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        db.record_run("RUN-BAAAAAAAAAAA", started_at="2026-06-01T00:00:00+00:00", status="passed")
        outcomes = [
            Outcome(
                run_id="RUN-BAAAAAAAAAAA",
                module="m",
                test_id=f"t{i}",
                outcome="failed" if i % 2 == 0 else "passed",
            )
            for i in range(10)
        ]
        db.record_outcomes(outcomes)
        stats = db.stats()
        assert stats["outcomes"] == 10
    finally:
        db.close()


def test_record_outcomes_no_op_on_empty_list(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        db.record_outcomes([])
        assert db.stats() == {"runs": 0, "outcomes": 0}
    finally:
        db.close()


def test_record_run_replaces_on_same_id(tmp_path: Path) -> None:
    db = FlakeDb.open(tmp_path / "flake.db")
    try:
        db.record_run("RUN-CAAAAAAAAAAA", "2026-06-01T00:00:00+00:00", "passed")
        db.record_run("RUN-CAAAAAAAAAAA", "2026-06-01T00:01:00+00:00", "failed")
        assert db.stats()["runs"] == 1
    finally:
        db.close()


def test_context_manager_closes(tmp_path: Path) -> None:
    with FlakeDb.open(tmp_path / "flake.db") as db:
        db.record_run("RUN-DAAAAAAAAAAA", "2026-06-01T00:00:00+00:00", "passed")
        assert db.stats()["runs"] == 1


def test_skipped_outcomes_do_not_count_as_failures(tmp_path: Path) -> None:
    with FlakeDb.open(tmp_path / "flake.db") as db:
        for i in range(10):
            run_id = f"RUN-EAAAAAAA{i:04d}"
            db.record_run(run_id, f"2026-06-01T00:{i:02d}:00+00:00", "passed")
            db.record_outcome(
                Outcome(
                    run_id=run_id,
                    module="m",
                    test_id="t",
                    outcome="skipped",
                )
            )
        stat = db.flake_rate("m", "t")
        assert stat.runs == 10
        assert stat.failures == 0
        assert stat.rate == 0.0
