# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Real-User Monitoring lite — receiver + schema (v1.9.0, phase 39).

The synthetic Playwright runner already emits JSONL events that the
reporter consumes (see ``engine/orchestrator/ts_bridge.py``). The RUM
SDK at ``packages/rum-browser-sdk/`` emits the same event shape from a
real user's browser. This module ingests that JSONL into the existing
artifact tree so reporter + scoring work unchanged.

A "RUM run" is just a synthetic run that didn't drive Playwright:

* Events follow the same wire schema (``schema_version`` + ``type`` +
  ``seq`` + ``ts``).
* Ingestion writes ``run.json``, ``findings.json``, and the events log
  into a fresh ``RUN-`` directory under the configured runs root.
* Downstream reporter / SDK / MCP read it just like a synthetic run.

This is intentionally MVP. The full RUM product (sampling controls,
sessionization, replay, redaction policy) is downstream work; we ship
the receiver + schema first so SDK authors can prototype against a
stable target.
"""

from __future__ import annotations

from engine.rum.ingest import (
    RumIngestError,
    RumIngestResult,
    RumSession,
    ingest_jsonl,
)
from engine.rum.schema import (
    RUM_EVENT_KINDS,
    RUM_SCHEMA_VERSION,
    RumEvent,
    parse_event,
)

__all__ = [
    "RUM_EVENT_KINDS",
    "RUM_SCHEMA_VERSION",
    "RumEvent",
    "RumIngestError",
    "RumIngestResult",
    "RumSession",
    "ingest_jsonl",
    "parse_event",
]
