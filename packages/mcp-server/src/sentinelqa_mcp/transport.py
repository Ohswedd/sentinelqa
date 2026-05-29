"""Transports for the MCP server (ADR-0023).

Two transports ship in Phase 18:

- :class:`StdioTransport` — NDJSON over stdin/stdout. The MCP base
  transport. This is what Claude Desktop uses.
- :class:`LoopbackHttpTransport` — minimal asyncio-based HTTP loop
  serving JSON-RPC POSTs on ``127.0.0.1``. **Loopback only**: refuses
  any non-loopback bind. Used for local development and tests that need
  a real socket without going through stdio.

Both transports speak a uniform :class:`Transport` Protocol so the
server doesn't care which one is plugged in.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import sys
from collections.abc import Awaitable, Callable
from typing import IO, Any, Protocol

# A handler receives a single decoded JSON-RPC request (or notification)
# and returns the JSON-RPC response dict to send back. Returning ``None``
# means "this was a notification; do not write a reply."
RequestHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


class Transport(Protocol):
    """A transport runs until the peer closes the connection."""

    async def serve(self, handle_request: RequestHandler) -> None: ...


class StdioTransport:
    """NDJSON over stdin/stdout (the MCP base transport).

    One JSON object per line. ``\\n`` framed. UTF-8.

    Logs MUST go to stderr only — stdout is reserved for wire bytes.
    The CLI command takes care of pointing the engine logger at stderr
    before constructing this transport.
    """

    def __init__(
        self,
        *,
        reader: IO[str] | None = None,
        writer: IO[str] | None = None,
    ) -> None:
        self._reader: IO[str] = reader if reader is not None else sys.stdin
        self._writer: IO[str] = writer if writer is not None else sys.stdout

    async def serve(self, handle_request: RequestHandler) -> None:
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, self._reader.readline)
            if line == "":
                # EOF — peer closed the pipe; exit cleanly.
                return
            stripped = line.strip()
            if not stripped:
                continue
            try:
                request = json.loads(stripped)
            except json.JSONDecodeError as exc:
                error_reply = _wire_parse_error(stripped, exc)
                await self._write(error_reply)
                continue
            response = await handle_request(request)
            if response is not None:
                await self._write(response)

    async def _write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._writer.write, line)
        await loop.run_in_executor(None, self._writer.flush)


class LoopbackHttpTransport:
    """Minimal HTTP/1.1 loop serving JSON-RPC POSTs on loopback.

    Accepts ``POST /`` with ``Content-Type: application/json``. The
    body is a single JSON-RPC request. The response is the JSON-RPC
    response with ``Content-Type: application/json``.

    This is intentionally not a production HTTP server — it is a local
    development convenience. ``host`` is forced to a loopback address
    (``127.0.0.1`` / ``::1``); any other bind raises ``ValueError``.
    """

    def __init__(self, port: int, *, host: str = "127.0.0.1") -> None:
        addr = ipaddress.ip_address(host)
        if not addr.is_loopback:
            raise ValueError(
                f"LoopbackHttpTransport refuses non-loopback host {host!r}; "
                "use 127.0.0.1 or ::1 (ADR-0023 safety contract)."
            )
        if not (1 <= port <= 65535):
            raise ValueError(f"port {port} out of range")
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._handle_request: RequestHandler | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def serve(self, handle_request: RequestHandler) -> None:
        self._handle_request = handle_request
        self._server = await asyncio.start_server(self._handle_connection, self._host, self._port)
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server.wait_closed()
            self._server = None

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_bytes = await _read_http_request(reader)
            if request_bytes is None:
                return
            response_payload = await self._handle_http_body(request_bytes)
            await _write_http_response(writer, response_payload)
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    async def _handle_http_body(self, body: bytes) -> dict[str, Any]:
        try:
            request = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _wire_parse_error(body.decode("utf-8", errors="replace"), exc)
        assert self._handle_request is not None
        response = await self._handle_request(request)
        if response is None:
            # Notifications still need an HTTP response — return an empty
            # 204-style payload as a JSON object so the wire stays valid.
            return {"jsonrpc": "2.0", "id": None, "result": None}
        return response


# ---------------------------------------------------------------------------
# Internal HTTP helpers — intentionally minimal.
# ---------------------------------------------------------------------------


async def _read_http_request(reader: asyncio.StreamReader) -> bytes | None:
    """Read a single ``POST /`` request and return its body bytes."""

    header_chunk = await reader.readuntil(b"\r\n\r\n")
    header_lines = header_chunk.split(b"\r\n")
    if not header_lines:
        return None
    request_line = header_lines[0].decode("ascii", errors="replace")
    parts = request_line.split(" ")
    if len(parts) < 3 or parts[0].upper() != "POST":
        # We only speak POST / — anything else gets a 405.
        return b""
    headers: dict[str, str] = {}
    for line in header_lines[1:]:
        if not line:
            continue
        if b":" not in line:
            continue
        k, _, v = line.decode("latin-1").partition(":")
        headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return b""
    return await reader.readexactly(length)


async def _write_http_response(writer: asyncio.StreamWriter, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )
    writer.write(headers + body)
    await writer.drain()


def _wire_parse_error(raw: str, exc: Exception) -> dict[str, Any]:
    """Build a JSON-RPC -32700 parse-error response for a malformed line."""

    return {
        "jsonrpc": "2.0",
        "id": None,
        "error": {
            "code": -32700,
            "message": "Parse error",
            "data": {"reason": str(exc), "fragment": raw[:120]},
        },
    }


__all__ = [
    "LoopbackHttpTransport",
    "RequestHandler",
    "StdioTransport",
    "Transport",
]
