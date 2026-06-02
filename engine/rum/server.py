# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Hosted RUM ingest endpoint (v1.11.0, phase 41).

`sentinel rum serve` lifts a small stdlib HTTP receiver that accepts
the JSONL stream produced by `@sentinelqa/rum`. Each POST appends the
delivered events to an inbox file under `<runs_root>/.rum-inbox/`;
periodically (and on shutdown) the receiver bakes the inbox into a
synthetic SentinelQA run via :func:`engine.rum.ingest.ingest_jsonl`.

The endpoint is loopback-only by default so a misconfiguration can't
leak user data; pass `--host 0.0.0.0` to expose it intentionally. CORS
is permissive on `OPTIONS` so the SDK can preflight cleanly.

Public entry points:

* :func:`handle_request` — pure router; takes the parsed envelope and
  returns an :class:`HttpResponse`. Used by tests directly.
* :func:`serve_forever` — wraps the router in a
  :class:`http.server.HTTPServer`.
"""

from __future__ import annotations

import json
import socketserver
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Final

from engine.rum.ingest import RumIngestError, RumIngestResult, ingest_jsonl

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 7332
_INBOX_DIRNAME: Final[str] = ".rum-inbox"
_DEFAULT_BAKE_THRESHOLD: Final[int] = 200


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Plain HTTP response carried back from the router."""

    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


@dataclass
class RumServerApp:
    """Receiver state, threaded through every router call."""

    runs_root: Path
    project_name: str = "rum"
    base_url: str = "https://rum.example.com"
    bake_threshold: int = _DEFAULT_BAKE_THRESHOLD
    on_bake: Callable[[RumIngestResult], None] | None = None
    _buffered_events: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    @property
    def inbox_dir(self) -> Path:
        return self.runs_root / _INBOX_DIRNAME

    @property
    def inbox_file(self) -> Path:
        return self.inbox_dir / "rum.jsonl"

    def append(self, body: bytes) -> int:
        """Append ``body`` to the inbox. Returns the count of valid lines."""

        added = 0
        with self.inbox_file.open("ab") as fh:
            for raw in body.splitlines():
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                fh.write(json.dumps(payload, sort_keys=True).encode("utf-8"))
                fh.write(b"\n")
                added += 1
        self._buffered_events += added
        return added

    def maybe_bake(self) -> RumIngestResult | None:
        """Bake the inbox if the buffer crossed the threshold."""

        if self._buffered_events < self.bake_threshold:
            return None
        return self.bake()

    def bake(self) -> RumIngestResult | None:
        """Bake the inbox into a synthetic run. No-op when the inbox is empty."""

        if not self.inbox_file.is_file() or self.inbox_file.stat().st_size == 0:
            self._buffered_events = 0
            return None
        try:
            result = ingest_jsonl(
                self.inbox_file,
                runs_root=self.runs_root,
                project_name=self.project_name,
                base_url=self.base_url,
            )
        except RumIngestError:
            self._buffered_events = 0
            self.inbox_file.unlink(missing_ok=True)
            return None
        self.inbox_file.unlink(missing_ok=True)
        self._buffered_events = 0
        if self.on_bake is not None:
            self.on_bake(result)
        return result


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


def _json_response(status: int, payload: object) -> HttpResponse:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    return HttpResponse(
        status=status,
        headers=(
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Access-Control-Allow-Origin", "*"),
        ),
        body=body,
    )


def _no_content_response() -> HttpResponse:
    return HttpResponse(
        status=204,
        headers=(
            ("Content-Length", "0"),
            ("Cache-Control", "no-store"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "content-type"),
        ),
        body=b"",
    )


def handle_request(
    app: RumServerApp,
    method: str,
    path: str,
    body: bytes,
) -> HttpResponse:
    """Pure router — easy to drive from tests without sockets."""

    if path == "/healthz" and method == "GET":
        return _json_response(200, {"status": "ok"})
    if path == "/rum" and method == "OPTIONS":
        return _no_content_response()
    if path == "/rum" and method == "POST":
        added = app.append(body)
        baked = app.maybe_bake()
        payload: dict[str, object] = {"received": added}
        if baked is not None:
            payload["baked_run_id"] = baked.run_id
            payload["sessions"] = len(baked.sessions)
        return _json_response(202, payload)
    if path == "/bake" and method == "POST":
        baked = app.bake()
        if baked is None:
            return _json_response(200, {"baked": False})
        return _json_response(
            200,
            {
                "baked": True,
                "run_id": baked.run_id,
                "events_processed": baked.events_processed,
                "sessions": len(baked.sessions),
            },
        )
    if method not in {"GET", "POST", "OPTIONS"}:
        return _json_response(405, {"error": "method not allowed"})
    return _json_response(404, {"error": "not found"})


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #


def _build_handler(app: RumServerApp) -> type[BaseHTTPRequestHandler]:
    class _RumHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b""
            response = handle_request(app, self.command, self.path, body)
            self.send_response(response.status)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            if response.body:
                self.wfile.write(response.body)

        def do_GET(self) -> None:  # noqa: N802 — http.server callback
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802 — http.server callback
            self._dispatch()

        def do_OPTIONS(self) -> None:  # noqa: N802 — http.server callback
            self._dispatch()

    return _RumHandler


def serve_forever(
    app: RumServerApp,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    on_ready: Callable[[str, int], None] | None = None,
) -> None:
    """Block, serving ``app`` on (host, port). Bakes inbox on shutdown."""

    handler_cls = _build_handler(app)

    class _Server(socketserver.TCPServer):
        allow_reuse_address = True

    with _Server((host, port), handler_cls) as server:
        if on_ready is not None:
            on_ready(host, port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.bake()


__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "HttpResponse",
    "RumServerApp",
    "handle_request",
    "serve_forever",
]
