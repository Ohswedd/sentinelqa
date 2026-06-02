# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""RUM replay view (v1.11.0, phase 41).

Renders a RUM run's session timeline + per-event log as a static HTML
page. Pure-Python rendering, consistent with the rest of the viewer:
no JS framework, no client-side state, no XSS surface.

The replay reads two artefacts the receiver writes:

* ``sessions.json`` — the per-session summary aggregated at ingest
  time.
* ``events.jsonl`` — the raw event stream, kept around so the replay
  can show per-event detail.

If either is missing (run isn't a RUM run, or sessions weren't
correlated for some reason) the route returns 404.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


def build_replay_payload(runs_root: Path, run_id: str) -> dict[str, Any] | None:
    run_dir = runs_root / run_id
    if not run_dir.is_dir():
        return None
    sessions_path = run_dir / "sessions.json"
    events_path = run_dir / "events.jsonl"
    if not sessions_path.is_file() or not events_path.is_file():
        return None
    try:
        sessions_payload = json.loads(sessions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(sessions_payload, dict):
        return None
    sessions = sessions_payload.get("sessions", [])
    if not isinstance(sessions, list):
        return None
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    by_session: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        session_id = str(event.get("session_id", "anonymous"))
        by_session.setdefault(session_id, []).append(event)
    return {
        "run_id": run_id,
        "sessions": sessions,
        "events_by_session": by_session,
        "total_events": len(events),
    }


def render_replay_html(run_id: str, payload: dict[str, Any]) -> str:
    sessions = payload.get("sessions", [])
    by_session = payload.get("events_by_session", {})
    total_events = payload.get("total_events", 0)

    session_blocks: list[str] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        session_id = str(session.get("session_id", "anonymous"))
        events = by_session.get(session_id, [])
        event_rows = "".join(_render_event_row(e) for e in events)
        session_blocks.append(
            _render_session_block(
                session_id=session_id,
                event_count=int(session.get("event_count", 0)),
                page_views=int(session.get("page_views", 0)),
                errors=int(session.get("errors", 0)),
                started_at=str(session.get("started_at", "")),
                ended_at=str(session.get("ended_at", "")),
                event_rows=event_rows,
            )
        )

    body = (
        "\n".join(session_blocks)
        if session_blocks
        else ('<p class="empty">No sessions found for this run.</p>')
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f"    <title>RUM replay — {escape(run_id)}</title>\n"
        '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"    <style>{_REPLAY_CSS}</style>\n"
        "  </head>\n"
        "  <body>\n"
        f"    <h1>RUM replay — {escape(run_id)}</h1>\n"
        f'    <p class="summary">{len(sessions)} session(s), '
        f"{int(total_events)} event(s) total.</p>\n"
        f"    {body}\n"
        "  </body>\n"
        "</html>\n"
    )


def _render_session_block(
    *,
    session_id: str,
    event_count: int,
    page_views: int,
    errors: int,
    started_at: str,
    ended_at: str,
    event_rows: str,
) -> str:
    err_class = "errors" if errors > 0 else ""
    return (
        f'<section class="session {err_class}">'
        f"<header><h2>{escape(session_id)}</h2>"
        f"<dl>"
        f"<dt>events</dt><dd>{event_count}</dd>"
        f"<dt>page views</dt><dd>{page_views}</dd>"
        f"<dt>errors</dt><dd>{errors}</dd>"
        f"<dt>started</dt><dd>{escape(started_at)}</dd>"
        f"<dt>ended</dt><dd>{escape(ended_at)}</dd>"
        f"</dl></header>"
        f"<table><thead><tr>"
        f"<th>seq</th><th>ts</th><th>type</th><th>detail</th>"
        f"</tr></thead><tbody>{event_rows}</tbody></table>"
        f"</section>"
    )


def _render_event_row(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "?"))
    row_class = "event-error" if event_type == "page.error" else ""
    detail_pairs = {
        k: v
        for k, v in event.items()
        if k not in {"schema_version", "type", "seq", "ts", "session_id"}
    }
    detail = ", ".join(f"{escape(str(k))}={escape(str(v))}" for k, v in detail_pairs.items())
    return (
        f"<tr class=\"{row_class}\">"
        f"<td>{int(event.get('seq', 0))}</td>"
        f"<td>{escape(str(event.get('ts', '')))}</td>"
        f"<td>{escape(event_type)}</td>"
        f"<td>{detail or '&mdash;'}</td>"
        f"</tr>"
    )


_REPLAY_CSS = """
:root { color-scheme: light dark; }
body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       margin: 0; padding: 24px; max-width: 1024px; }
h1 { margin: 0 0 8px; font-size: 20px; }
.summary { color: #475569; margin: 0 0 24px; }
.empty { color: #475569; }
section.session { border: 1px solid #cbd5e1; border-radius: 8px;
                  margin: 16px 0; padding: 16px; }
section.session.errors { border-color: #f87171; background: #fef2f2; }
section.session header { display: flex; align-items: baseline; gap: 12px;
                         flex-wrap: wrap; }
section.session h2 { margin: 0; font-size: 16px; }
section.session dl { display: flex; gap: 12px; margin: 0; font-size: 12px;
                     color: #334155; }
section.session dt { font-weight: 600; }
section.session dd { margin: 0; }
table { width: 100%; border-collapse: collapse; margin-top: 12px;
        font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; }
th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #e2e8f0; }
th { background: #f1f5f9; }
tr.event-error td { background: #fef2f2; color: #7f1d1d; }
"""


__all__ = ["build_replay_payload", "render_replay_html"]
