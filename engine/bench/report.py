# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Bench report dataclasses + JSON round-trip."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BenchMetric:
    """One metric: name + value (seconds) + sample count.

    ``samples`` reports how many independent measurements were averaged
    to produce ``value_seconds``. Reporters use it to colour
    high-variance metrics; the baseline comparator does not.
    """

    name: str
    value_seconds: float
    samples: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BenchReport:
    """Wire-stable output of :func:`engine.bench.run_bench`."""

    schema_version: str = "1"
    sentinelqa_version: str = ""
    metrics: tuple[BenchMetric, ...] = field(default_factory=tuple)

    def metric(self, name: str) -> BenchMetric:
        for m in self.metrics:
            if m.name == name:
                return m
        raise KeyError(f"no metric named {name!r} in BenchReport")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sentinelqa_version": self.sentinelqa_version,
            "metrics": [m.to_dict() for m in self.metrics],
        }


def write_report(path: Path, report: BenchReport) -> Path:
    """Serialise ``report`` to ``path`` with sorted keys + LF endings."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.to_dict(), sort_keys=True, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def load_report(path: Path) -> BenchReport:
    """Round-trip a previously-written report from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = tuple(
        BenchMetric(
            name=str(entry["name"]),
            value_seconds=float(entry["value_seconds"]),
            samples=int(entry["samples"]),
        )
        for entry in payload.get("metrics", [])
    )
    return BenchReport(
        schema_version=str(payload.get("schema_version", "1")),
        sentinelqa_version=str(payload.get("sentinelqa_version", "")),
        metrics=metrics,
    )


__all__ = [
    "BenchMetric",
    "BenchReport",
    "load_report",
    "write_report",
]
