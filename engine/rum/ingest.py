# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Ingest a RUM JSONL stream into a synthetic SentinelQA run.

The receiver:

1. Reads ``rum.jsonl`` line by line.
2. Parses each line into a :class:`RumEvent` (tolerant: bad lines log
   as ``parse_errors`` and don't kill the run).
3. Synthesises a minimal ``run.json`` + ``events.jsonl`` +
   ``findings.json`` under ``<runs_root>/<run_id>/``.
4. Derives a tiny set of findings from ``page.error`` events so the
   existing reporter / scoring chain has something to act on.

The output directory is *byte-equivalent* to a discover-only synthetic
run with no findings — the reporter, SDK, and MCP server consume it
identically. This is what lets RUM data flow through the same gates as
synthetic data without forking the engine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from engine.rum.schema import RumEvent, parse_event


class RumIngestError(Exception):
    """Raised when the input stream is structurally unusable."""


@dataclass(frozen=True, slots=True)
class RumSession:
    """One real-user session aggregated from the JSONL stream."""

    session_id: str
    event_count: int
    page_views: int
    errors: int
    started_at: str
    ended_at: str


@dataclass(frozen=True, slots=True)
class RumIngestResult:
    """Outcome of one ingestion."""

    run_id: str
    run_dir: Path
    events_processed: int
    parse_errors: int
    findings_emitted: int
    sessions: tuple[RumSession, ...] = ()


def ingest_jsonl(
    source: Path,
    *,
    runs_root: Path,
    project_name: str = "rum",
    base_url: str = "https://rum.example.com",
    now: datetime | None = None,
) -> RumIngestResult:
    """Ingest a RUM JSONL stream into a synthetic run.

    ``runs_root`` is typically ``.sentinel/runs/``. ``base_url`` is the
    pretty target the run is associated with — RUM doesn't probe a
    specific URL, so callers pass the customer-facing host here.
    """

    if not source.is_file():
        raise RumIngestError(f"RUM input not found: {source}")

    events, parse_errors = _parse_stream(source)
    if not events:
        raise RumIngestError(f"RUM input had no parsable events: {source}")

    now = (now or datetime.now(UTC)).astimezone(UTC)
    run_id = _derive_run_id(source, events, now)
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _write_events(run_dir / "events.jsonl", events)
    sessions = _sessions_from_events(events)
    _write_sessions(run_dir / "sessions.json", sessions, run_id=run_id, now=now)
    findings = _derive_findings(events, run_id=run_id, now=now)
    _write_findings(run_dir / "findings.json", findings, run_id=run_id, now=now)
    _write_run_json(
        run_dir / "run.json",
        run_id=run_id,
        project_name=project_name,
        base_url=base_url,
        events_processed=len(events),
        findings_count=len(findings),
        sessions=sessions,
        now=now,
    )

    return RumIngestResult(
        run_id=run_id,
        run_dir=run_dir,
        events_processed=len(events),
        parse_errors=parse_errors,
        findings_emitted=len(findings),
        sessions=sessions,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_stream(source: Path) -> tuple[list[RumEvent], int]:
    events: list[RumEvent] = []
    parse_errors = 0
    for line in source.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(payload, dict):
            parse_errors += 1
            continue
        events.append(parse_event(payload))
    return events, parse_errors


def _derive_run_id(source: Path, events: list[RumEvent], now: datetime) -> str:
    """Derive a deterministic run id from the source path + first event ts.

    The id needs to be stable across re-runs of the same input (so users
    don't accumulate duplicate runs from a retried CI step), but unique
    when the input changes.
    """

    digest = hashlib.sha256()
    digest.update(str(source.resolve()).encode("utf-8"))
    digest.update(b"|")
    digest.update(events[0].ts.encode("utf-8"))
    digest.update(b"|")
    digest.update(str(len(events)).encode("utf-8"))
    suffix = digest.hexdigest()[:12].upper()
    return f"RUN-{suffix}"


def _write_events(path: Path, events: list[RumEvent]) -> None:
    """Persist the events.jsonl shadow log."""

    lines = []
    for event in events:
        lines.append(
            json.dumps(
                {
                    "schema_version": event.schema_version,
                    "type": event.type,
                    "seq": event.seq,
                    "ts": event.ts,
                    **event.payload,
                },
                sort_keys=True,
            )
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _sessions_from_events(events: list[RumEvent]) -> tuple[RumSession, ...]:
    """Group events into sessions by ``payload.session_id``.

    Events without an explicit session id are bucketed under
    ``"anonymous"`` so they still show up in the summary; this also
    keeps the downstream contract simple (every event lands in exactly
    one session).
    """

    buckets: dict[str, list[RumEvent]] = {}
    for event in events:
        session_id = str(event.payload.get("session_id", "anonymous"))
        buckets.setdefault(session_id, []).append(event)

    sessions: list[RumSession] = []
    for session_id, bucket in buckets.items():
        timestamps = [e.ts for e in bucket if e.ts]
        sessions.append(
            RumSession(
                session_id=session_id,
                event_count=len(bucket),
                page_views=sum(1 for e in bucket if e.type == "page.view"),
                errors=sum(1 for e in bucket if e.type == "page.error"),
                started_at=min(timestamps) if timestamps else "",
                ended_at=max(timestamps) if timestamps else "",
            )
        )
    return tuple(sorted(sessions, key=lambda s: s.session_id))


def _write_sessions(
    path: Path, sessions: tuple[RumSession, ...], *, run_id: str, now: datetime
) -> None:
    payload = {
        "schema_version": "1",
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "count": len(sessions),
        "sessions": [
            {
                "session_id": s.session_id,
                "event_count": s.event_count,
                "page_views": s.page_views,
                "errors": s.errors,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
            }
            for s in sessions
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _derive_findings(
    events: list[RumEvent], *, run_id: str, now: datetime
) -> list[dict[str, object]]:
    """Turn ``page.error`` events into typed findings.

    Each unique (route, message) pair becomes one finding. Findings are
    emitted with severity ``high`` (RUM errors are real-user observed,
    so they're not noise the way synthetic console.error sometimes is).
    """

    seen: set[tuple[str, str]] = set()
    out: list[dict[str, object]] = []
    for event in events:
        if event.type != "page.error":
            continue
        route = str(event.payload.get("route", ""))
        message = str(event.payload.get("message", "")).strip()[:1000]
        key = (route, message)
        if key in seen or not message:
            continue
        seen.add(key)
        out.append(
            {
                "id": _stable_finding_id("rum", run_id, route, message),
                "run_id": run_id,
                "module": "rum",
                "category": "rum_page_error",
                "severity": "high",
                "confidence": 0.9,
                "title": f"Real-user page error on {route or '/'}",
                "description": message or "Real-user-observed uncaught error.",
                "location": {
                    "route": route or None,
                    "selector": None,
                    "file": None,
                    "line": None,
                },
                "evidence": [],
                "reproduction_steps": [],
                "suggested_fix": None,
                "affected_target": None,
                "recommendation": (
                    "Open this URL in the browser, reproduce the path the "
                    "user took, and fix the underlying error."
                ),
                "cwe_id": None,
                "attack_id": None,
                "owasp_api_id": None,
                "compliance_id": None,
                "attestation": None,
                "created_at": now.isoformat(),
                "schema_version": "2",
            }
        )
    return out


def _write_findings(
    path: Path, findings: list[dict[str, object]], *, run_id: str, now: datetime
) -> None:
    envelope = {
        "schema_version": "2",
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "count": len(findings),
        "findings": findings,
    }
    path.write_text(json.dumps(envelope, sort_keys=True, indent=2), encoding="utf-8")


def _write_run_json(
    path: Path,
    *,
    run_id: str,
    project_name: str,
    base_url: str,
    events_processed: int,
    findings_count: int,
    sessions: tuple[RumSession, ...],
    now: datetime,
) -> None:
    payload = {
        "run_id": run_id,
        "status": "passed" if findings_count == 0 else "failed",
        "modules_run": ["rum"],
        "target": {"base_url": base_url, "host": ""},
        "project": {"name": project_name},
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "summary": {
            "passed": 0,
            "failed": findings_count,
            "blocked": 0,
            "info": 0,
        },
        "rum": {
            "events_processed": events_processed,
            "schema_version": "1",
            "session_count": len(sessions),
            "sessions_with_errors": sum(1 for s in sessions if s.errors > 0),
        },
    }
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _stable_finding_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12].upper()
    return f"FND-{digest}"


__all__ = ["RumIngestError", "RumIngestResult", "RumSession", "ingest_jsonl"]
