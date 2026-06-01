# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""``cache.json`` — per-run cache + fingerprint observability artifact.

This artifact is a *new* file written under ``.sentinel/runs/<id>/``;
it does not change the existing ``run.json`` wire schema. It records:

* the source fingerprint computed at the start of the run;
* whether discovery / plan cache lookups hit or missed;
* the cache key the lookup used.

The artifact is the source of truth for ``sentinel audit --since`` —
that command reads the prior run's ``cache.json`` to compare
fingerprints and decide whether anything needs to re-run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CACHE_REPORT_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class CachePhaseInfo:
    """Per-phase cache info (discovery and plan look identical)."""

    cache_hit: bool | None = None
    cache_key: str | None = None


@dataclass(frozen=True, slots=True)
class FingerprintInfo:
    """Source fingerprint summary recorded in ``cache.json``."""

    hash: str
    short: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class CacheReport:
    """``cache.json`` envelope."""

    schema_version: str = CACHE_REPORT_SCHEMA_VERSION
    source_fingerprint: FingerprintInfo | None = None
    discovery: CachePhaseInfo = field(default_factory=CachePhaseInfo)
    plan: CachePhaseInfo = field(default_factory=CachePhaseInfo)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "source_fingerprint": (
                asdict(self.source_fingerprint) if self.source_fingerprint is not None else None
            ),
            "discovery": asdict(self.discovery),
            "plan": asdict(self.plan),
        }
        return payload


def write_cache_report(path: Path, report: CacheReport) -> Path:
    """Write ``cache.json`` (deterministic key order, 2-space indent)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(report.to_dict(), sort_keys=True, indent=2) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def read_cache_report(path: Path) -> CacheReport | None:
    """Read ``cache.json`` from a completed run. Returns ``None`` if missing or malformed."""

    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fp_raw = raw.get("source_fingerprint")
    fp = (
        FingerprintInfo(
            hash=str(fp_raw["hash"]),
            short=str(fp_raw["short"]),
            file_count=int(fp_raw["file_count"]),
            total_bytes=int(fp_raw["total_bytes"]),
        )
        if isinstance(fp_raw, dict)
        else None
    )
    discovery_raw = raw.get("discovery") or {}
    plan_raw = raw.get("plan") or {}
    return CacheReport(
        schema_version=str(raw.get("schema_version", CACHE_REPORT_SCHEMA_VERSION)),
        source_fingerprint=fp,
        discovery=CachePhaseInfo(
            cache_hit=discovery_raw.get("cache_hit"),
            cache_key=discovery_raw.get("cache_key"),
        ),
        plan=CachePhaseInfo(
            cache_hit=plan_raw.get("cache_hit"),
            cache_key=plan_raw.get("cache_key"),
        ),
    )


__all__ = [
    "CACHE_REPORT_SCHEMA_VERSION",
    "CachePhaseInfo",
    "CacheReport",
    "FingerprintInfo",
    "read_cache_report",
    "write_cache_report",
]
