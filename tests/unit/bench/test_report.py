# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the BenchReport / BenchMetric round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.bench import BenchMetric, BenchReport, load_report, write_report


def _report() -> BenchReport:
    return BenchReport(
        sentinelqa_version="1.8.0",
        metrics=(
            BenchMetric(name="import_time_s", value_seconds=0.42, samples=3),
            BenchMetric(name="full_audit_s", value_seconds=1.5, samples=2),
        ),
    )


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "bench.json"
    write_report(path, _report())
    loaded = load_report(path)
    assert loaded == _report()


def test_metric_lookup() -> None:
    report = _report()
    assert report.metric("import_time_s").value_seconds == 0.42
    with pytest.raises(KeyError):
        report.metric("does_not_exist")


def test_write_report_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "bench.json"
    write_report(path, _report())
    assert path.is_file()


def test_write_report_is_stable_bytes(tmp_path: Path) -> None:
    """The same report must serialise to byte-identical JSON across calls."""

    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    write_report(path_a, _report())
    write_report(path_b, _report())
    assert path_a.read_bytes() == path_b.read_bytes()


def test_to_dict_shape() -> None:
    payload = _report().to_dict()
    assert payload["schema_version"] == "1"
    assert payload["sentinelqa_version"] == "1.8.0"
    assert isinstance(payload["metrics"], list)
    assert payload["metrics"][0]["name"] == "import_time_s"
