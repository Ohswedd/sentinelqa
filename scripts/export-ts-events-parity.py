#!/usr/bin/env python
"""Generate the cross-language TS-events parity fixture.

The fixture (``tests/golden/ts-events/sample.jsonl``) contains one
event per line, covering every event kind in
``packages/shared-schema/ts-events.schema.json``. Both the Python
parser and the TS parseEvent() consume the same bytes; CI fails if
either side disagrees.

Modes:

  python scripts/export-ts-events-parity.py          # write the file
  python scripts/export-ts-events-parity.py --check  # fail if stale

Idempotent: re-running with no changes produces a byte-identical
output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "tests" / "golden" / "ts-events" / "sample.jsonl"

PROTOCOL_VERSION = "1.0.0"
RUN_STARTED = "2026-05-28T00:00:00.000Z"
RUN_FINISHED = "2026-05-28T00:00:05.000Z"


def _envelope(seq: int, ts_offset_ms: int) -> dict[str, Any]:
    base_ms = 0
    total_ms = base_ms + ts_offset_ms
    seconds = total_ms // 1000
    millis = total_ms % 1000
    # All timestamps are anchored at 2026-05-28T00:00:00Z + offset.
    ts = f"2026-05-28T00:00:{seconds:02d}.{millis:03d}Z"
    return {"schema_version": PROTOCOL_VERSION, "seq": seq, "ts": ts}


SAMPLE_EVENTS: list[dict[str, Any]] = [
    {
        "type": "run.start",
        **_envelope(1, 0),
        "run_id": "run-parity-1",
        "target": "http://localhost:3000",
        "started_at": RUN_STARTED,
    },
    {
        "type": "test.start",
        **_envelope(2, 100),
        "test_id": "t-login",
        "title": "logs in",
        "file": "tests/login.spec.ts",
    },
    {
        "type": "step.start",
        **_envelope(3, 150),
        "test_id": "t-login",
        "step_id": "s-1",
        "name": "fill email",
    },
    {
        "type": "network.request",
        **_envelope(4, 160),
        "test_id": "t-login",
        "request_id": "req-1",
        "url": "https://example.com/api/login",
        "method": "POST",
        "content_length": 42,
        "content_type": "application/json",
    },
    {
        "type": "network.response",
        **_envelope(5, 280),
        "test_id": "t-login",
        "request_id": "req-1",
        "url": "https://example.com/api/login",
        "status": 200,
        "duration_ms": 120,
        "content_length": 128,
        "content_type": "application/json",
    },
    {
        "type": "console",
        **_envelope(6, 300),
        "test_id": "t-login",
        "level": "warn",
        "message": "session cookie missing HttpOnly",
        "source": "console.warn",
    },
    {
        "type": "step.end",
        **_envelope(7, 400),
        "test_id": "t-login",
        "step_id": "s-1",
        "duration_ms": 250,
        "ok": True,
    },
    {
        "type": "evidence",
        **_envelope(8, 450),
        "test_id": "t-login",
        "step_id": None,
        "evidence_kind": "screenshot",
        "path": ".sentinel/runs/r/screenshots/login.png",
        "label": "after-login",
    },
    {
        "type": "dom.snapshot",
        **_envelope(9, 460),
        "test_id": "t-login",
        "step_id": None,
        "path": ".sentinel/runs/r/dom/login.html",
        "label": "after-login",
    },
    {
        "type": "test.end",
        **_envelope(10, 500),
        "test_id": "t-login",
        "duration_ms": 480,
        "status": "passed",
        "retries": 0,
    },
    {
        "type": "test.start",
        **_envelope(11, 600),
        "test_id": "t-checkout",
        "title": "checkout flow",
        "file": "tests/checkout.spec.ts",
    },
    {
        "type": "step.start",
        **_envelope(12, 620),
        "test_id": "t-checkout",
        "step_id": "s-2",
        "name": "click pay",
    },
    {
        "type": "step.end",
        **_envelope(13, 700),
        "test_id": "t-checkout",
        "step_id": "s-2",
        "duration_ms": 80,
        "ok": False,
        "error": {
            "name": "Error",
            "message": "selector not found: [data-testid=pay]",
            "stack": "Error: selector not found...\n  at /tests/checkout.spec.ts:10:5",
        },
    },
    {
        "type": "test.end",
        **_envelope(14, 800),
        "test_id": "t-checkout",
        "duration_ms": 200,
        "status": "failed",
        "retries": 1,
        "error": {
            "name": "Error",
            "message": "selector not found",
        },
    },
    {
        "type": "evidence",
        **_envelope(15, 810),
        "test_id": "t-checkout",
        "step_id": None,
        "evidence_kind": "trace",
        "path": ".sentinel/runs/r/traces/checkout.zip",
        "label": "trace",
    },
    {
        "type": "module.event",
        **_envelope(16, 820),
        "module": "accessibility",
        "name": "axe-violation",
        "payload": {"id": "color-contrast", "impact": "serious"},
    },
    {
        "type": "log",
        **_envelope(17, 830),
        "level": "info",
        "msg": "run finished",
        "fields": {"tests": 2, "failed": 1},
    },
    {
        "type": "error",
        **_envelope(18, 840),
        "code": "PW_INTERNAL",
        "message": "context closed unexpectedly",
    },
    {
        "type": "run.end",
        **_envelope(19, 5000),
        "run_id": "run-parity-1",
        "finished_at": RUN_FINISHED,
        "status": "failed",
        "tests_total": 2,
        "tests_failed": 1,
    },
]


def _serialize(events: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(ev, ensure_ascii=True) + "\n" for ev in events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = _serialize(SAMPLE_EVENTS)
    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} is missing", file=sys.stderr)
            return 1
        if TARGET.read_text() != rendered:
            print(
                f"{TARGET} is stale. "
                f"Run `python scripts/export-ts-events-parity.py` to refresh.",
                file=sys.stderr,
            )
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
