# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Stdlib HTTP application for ``sentinel serve``.

We use :mod:`http.server` rather than FastAPI/Starlette so the runtime
dependency footprint of the CLI stays small. The router is a single
:func:`handle_request` function that takes a ``method`` + ``path`` +
the running-tree's ``runs_root`` and returns a
:class:`HttpResponse` tuple.

Routes:

* ``GET /``                            → run index HTML
* ``GET /healthz``                     → liveness probe
* ``GET /widget.js``                   → embeddable status widget
* ``GET /api/runs.json``               → ``{runs: [{run_id, ...}]}``
* ``GET /api/trends.json``             → trend timeseries
* ``GET /api/status.json``             → status snapshot for the widget
* ``GET /api/diff/<a>/<b>.json``       → :class:`RunDiff` as JSON
* ``GET /runs/<id>/<artifact>``        → serve any run artifact
* anything else                        → 404
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import socketserver
from collections.abc import Iterable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Final
from urllib.parse import unquote

from engine.reporter.history import (
    compute_history_series,
    compute_status_snapshot,
    render_status_widget_js,
)
from engine.reporter.run_diff import compute_run_diff

logger = logging.getLogger("sentinelqa.reporter.serve")

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 7331

_RUN_ID_RE: Final[re.Pattern[str]] = re.compile(r"^RUN-[A-Za-z0-9]+$")
_SAFE_ARTIFACT_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-]+$")

# Whitelist of artifact extensions the viewer is willing to serve.
_SERVE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".html",
        ".json",
        ".md",
        ".sarif",
        ".xml",
        ".css",
        ".js",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".webp",
        ".log",
        ".yaml",
        ".yml",
    }
)


class ViewerError(RuntimeError):
    """Raised on internal viewer routing problems."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Plain tuple-like value object holding the response."""

    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


@dataclass(frozen=True, slots=True)
class ViewerApp:
    """The view layer plus its dependencies."""

    runs_root: Path
    threshold: float = 80.0


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def _json_response(status: int, payload: object) -> HttpResponse:
    body = json.dumps(payload, sort_keys=True, default=_default_serializer).encode("utf-8")
    return HttpResponse(
        status=status,
        headers=(
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ),
        body=body,
    )


def _default_serializer(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def _text_response(
    status: int,
    body: str,
    *,
    content_type: str = "text/html; charset=utf-8",
) -> HttpResponse:
    encoded = body.encode("utf-8")
    return HttpResponse(
        status=status,
        headers=(
            ("Content-Type", content_type),
            ("Content-Length", str(len(encoded))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ),
        body=encoded,
    )


def _binary_response(
    status: int,
    body: bytes,
    *,
    content_type: str,
) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=(
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ),
        body=body,
    )


def render_index_html(app: ViewerApp) -> str:
    """Render the index page listing every available run."""

    from html import escape

    series = compute_history_series(app.runs_root)
    rows = "".join(
        f"<tr><td><a href='/runs/{escape(p.run_id)}/report.html'>"
        f"{escape(p.run_id)}</a></td>"
        f"<td>{escape(p.started_at)}</td>"
        f"<td>{p.quality_score if p.quality_score is not None else 'n/a'}</td>"
        f"<td>{escape(p.status)}</td></tr>"
        for p in reversed(series.points)
    )
    if not rows:
        rows = (
            "<tr><td colspan='4'><em>No runs yet. Run "
            "<code>sentinel audit</code> to populate.</em></td></tr>"
        )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>SentinelQA — run viewer</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,sans-serif;max-width:1080px;"
        "margin:2rem auto;padding:0 1rem;color:#111827;}"
        "h1{margin:0 0 1rem;font-size:1.4rem;}"
        "table{width:100%;border-collapse:collapse;}"
        "th,td{padding:.5rem .75rem;border-bottom:1px solid #e5e7eb;text-align:left;}"
        "th{font-size:.8rem;text-transform:uppercase;color:#6b7280;}"
        "a{color:#1d4ed8;text-decoration:none;}"
        "a:hover{text-decoration:underline;}"
        ".badges{display:flex;gap:.5rem;font-size:.85rem;margin:1rem 0;}"
        ".badge{padding:.25rem .5rem;background:#f3f4f6;border-radius:4px;}"
        "</style>"
        "</head><body>"
        "<h1>SentinelQA — run viewer</h1>"
        f"<div class='badges'>"
        f"<span class='badge'>runs root: {escape(str(app.runs_root))}</span>"
        f"<span class='badge'>runs in history: {len(series.points)}</span>"
        "</div>"
        "<table>"
        "<thead><tr><th>Run</th><th>Started</th><th>Score</th>"
        "<th>Status</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "<p><small>"
        "Endpoints: <code>/api/runs.json</code>, <code>/api/trends.json</code>, "
        "<code>/api/status.json</code>, <code>/api/diff/&lt;a&gt;/&lt;b&gt;.json</code>, "
        "<code>/widget.js</code>.</small></p>"
        "</body></html>"
    )


def _runs_index(app: ViewerApp) -> HttpResponse:
    series = compute_history_series(app.runs_root)
    payload = {
        "runs": [
            {
                "run_id": p.run_id,
                "started_at": p.started_at,
                "status": p.status,
                "quality_score": p.quality_score,
                "findings_by_severity": p.findings_by_severity,
            }
            for p in series.points
        ],
        "window": series.window,
    }
    return _json_response(int(HTTPStatus.OK), payload)


def _trends(app: ViewerApp) -> HttpResponse:
    series = compute_history_series(app.runs_root)
    payload = {
        "window": series.window,
        "score": [
            {"run_id": p.run_id, "x": p.started_at, "y": p.quality_score} for p in series.points
        ],
        "severity": {
            sev: [
                {
                    "run_id": p.run_id,
                    "x": p.started_at,
                    "y": p.findings_by_severity.get(sev, 0),
                }
                for p in series.points
            ]
            for sev in ("critical", "high", "medium", "low", "info")
        },
    }
    return _json_response(int(HTTPStatus.OK), payload)


def _status(app: ViewerApp) -> HttpResponse:
    snapshot = compute_status_snapshot(app.runs_root, threshold=app.threshold)
    if snapshot is None:
        return _json_response(
            int(HTTPStatus.OK),
            {
                "run_id": None,
                "status": "no-runs",
                "release_decision": "inconclusive",
                "quality_score": None,
                "updated_at": None,
                "findings_by_severity": {},
            },
        )
    return _json_response(int(HTTPStatus.OK), dataclasses.asdict(snapshot))


def _serve_widget() -> HttpResponse:
    return _text_response(
        int(HTTPStatus.OK),
        render_status_widget_js(),
        content_type="application/javascript; charset=utf-8",
    )


def _diff(app: ViewerApp, before_id: str, after_id: str) -> HttpResponse:
    if not _RUN_ID_RE.match(before_id) or not _RUN_ID_RE.match(after_id):
        return _json_response(int(HTTPStatus.BAD_REQUEST), {"error": "invalid run id"})
    before_dir = app.runs_root / before_id
    after_dir = app.runs_root / after_id
    if not before_dir.is_dir() or not after_dir.is_dir():
        return _json_response(int(HTTPStatus.NOT_FOUND), {"error": "unknown run"})
    diff = compute_run_diff(before_dir, after_dir)
    payload = {
        "before_run_id": diff.before_run_id,
        "after_run_id": diff.after_run_id,
        "has_changes": diff.has_changes,
        "comparison": {
            "score_delta": diff.comparison.score_delta,
            "has_regressions": diff.comparison.has_regressions,
            "new": [dataclasses.asdict(f) for f in diff.comparison.new],
            "resolved": [dataclasses.asdict(f) for f in diff.comparison.resolved],
            "persistent_count": len(diff.comparison.persistent),
            "severity_changes": [
                {
                    "module": c.after.module,
                    "title": c.after.title,
                    "before": c.before.severity,
                    "after": c.after.severity,
                    "direction": c.direction,
                }
                for c in diff.comparison.severity_changes
            ],
        },
        "artifact_deltas": [dataclasses.asdict(d) for d in diff.artifact_deltas],
    }
    return _json_response(int(HTTPStatus.OK), payload)


def _serve_run_artifact(app: ViewerApp, run_id: str, artifact: str) -> HttpResponse:
    if not _RUN_ID_RE.match(run_id):
        return _text_response(int(HTTPStatus.BAD_REQUEST), "invalid run id")
    if not _SAFE_ARTIFACT_RE.match(artifact):
        return _text_response(int(HTTPStatus.BAD_REQUEST), "invalid artifact name")
    target = (app.runs_root / run_id / artifact).resolve()
    runs_root_resolved = app.runs_root.resolve()
    # Defence-in-depth: never serve anything outside the runs root.
    try:
        target.relative_to(runs_root_resolved)
    except ValueError:
        return _text_response(int(HTTPStatus.BAD_REQUEST), "path traversal blocked")
    if not target.is_file():
        return _text_response(int(HTTPStatus.NOT_FOUND), "artifact not found")
    suffix = target.suffix.lower()
    if suffix not in _SERVE_EXTENSIONS:
        return _text_response(
            int(HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
            f"refusing to serve {suffix!r}",
        )
    raw = target.read_bytes()
    return _binary_response(
        int(HTTPStatus.OK),
        raw,
        content_type=_content_type_for(suffix),
    )


def _content_type_for(suffix: str) -> str:
    mapping = {
        ".html": "text/html; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".sarif": "application/sarif+json; charset=utf-8",
        ".xml": "application/xml; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".log": "text/plain; charset=utf-8",
        ".yaml": "application/yaml; charset=utf-8",
        ".yml": "application/yaml; charset=utf-8",
    }
    return mapping.get(suffix, "application/octet-stream")


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


def handle_request(app: ViewerApp, method: str, path: str) -> HttpResponse:
    """Pure router — drives every test, never touches sockets."""

    if method != "GET":
        return _text_response(int(HTTPStatus.METHOD_NOT_ALLOWED), "GET only")
    decoded = unquote(path).split("?", 1)[0]

    if decoded in {"", "/"}:
        return _text_response(int(HTTPStatus.OK), render_index_html(app))
    if decoded == "/healthz":
        return _text_response(int(HTTPStatus.OK), "ok", content_type="text/plain")
    if decoded == "/widget.js":
        return _serve_widget()
    if decoded == "/api/runs.json":
        return _runs_index(app)
    if decoded == "/api/trends.json":
        return _trends(app)
    if decoded == "/api/status.json":
        return _status(app)
    match = re.match(r"^/api/diff/([^/]+)/([^/]+)\.json$", decoded)
    if match:
        return _diff(app, match.group(1), match.group(2))
    match = re.match(r"^/runs/([^/]+)/rum$", decoded)
    if match:
        return _rum_replay(app, match.group(1))
    match = re.match(r"^/api/runs/([^/]+)/rum\.json$", decoded)
    if match:
        return _rum_replay_json(app, match.group(1))
    match = re.match(r"^/runs/([^/]+)/([^/]+)$", decoded)
    if match:
        return _serve_run_artifact(app, match.group(1), match.group(2))
    return _text_response(int(HTTPStatus.NOT_FOUND), "not found")


def _rum_replay_json(app: ViewerApp, run_id: str) -> HttpResponse:
    """Return the parsed sessions + events for a RUM run."""

    from engine.reporter.serve.rum_replay import build_replay_payload

    payload = build_replay_payload(app.runs_root, run_id)
    if payload is None:
        return _text_response(int(HTTPStatus.NOT_FOUND), "no RUM data for this run")
    return _json_response(int(HTTPStatus.OK), payload)


def _rum_replay(app: ViewerApp, run_id: str) -> HttpResponse:
    """Render the HTML replay page for a RUM run."""

    from engine.reporter.serve.rum_replay import build_replay_payload, render_replay_html

    payload = build_replay_payload(app.runs_root, run_id)
    if payload is None:
        return _text_response(int(HTTPStatus.NOT_FOUND), "no RUM data for this run")
    return _text_response(int(HTTPStatus.OK), render_replay_html(run_id, payload))


# --------------------------------------------------------------------------- #
# Stdlib server wiring
# --------------------------------------------------------------------------- #


def _make_handler_class(app: ViewerApp) -> type[BaseHTTPRequestHandler]:
    """Bind a :class:`ViewerApp` into a request handler class."""

    class _Handler(BaseHTTPRequestHandler):
        # Silence the default access log on stderr; the CLI prefers
        # nothing on success and a single line on error.
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            response = handle_request(app, self.command, self.path)
            self._write_response(response)

        def do_HEAD(self) -> None:  # noqa: N802
            response = handle_request(app, "GET", self.path)
            self.send_response(response.status)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()

        def _write_response(self, response: HttpResponse) -> None:
            self.send_response(response.status)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.body)

    return _Handler


def serve_forever(
    app: ViewerApp,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    on_ready: object = None,
) -> None:
    """Bind to ``(host, port)`` and serve until interrupted."""

    handler_class = _make_handler_class(app)

    class _Server(socketserver.TCPServer):
        allow_reuse_address = True

    with _Server((host, port), handler_class) as httpd:
        if on_ready is not None:
            try:
                on_ready(httpd.server_address)  # type: ignore[operator]
            except Exception as exc:
                logger.warning("on_ready callback raised: %s", exc)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return


def _iter_runs_for_test(app: ViewerApp) -> Iterable[str]:  # pragma: no cover - test seam
    for run_dir in app.runs_root.iterdir() if app.runs_root.is_dir() else ():
        yield run_dir.name


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "HttpResponse",
    "ViewerApp",
    "ViewerError",
    "handle_request",
    "render_index_html",
    "serve_forever",
]
