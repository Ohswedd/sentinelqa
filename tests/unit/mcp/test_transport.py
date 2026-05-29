"""Transport unit tests (stdio + loopback HTTP)."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from typing import Any

import pytest

from sentinelqa_mcp.transport import (
    LoopbackHttpTransport,
    RequestHandler,
    StdioTransport,
    _read_http_request,
    _wire_parse_error,
    _write_http_response,
)


def _echo_handler() -> RequestHandler:
    async def handle(message: dict[str, Any]) -> dict[str, Any] | None:
        if message.get("method") == "notify":
            return None
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": dict(message)}

    return handle


async def test_stdio_round_trips_ndjson() -> None:
    reader = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"echo"}\n')
    writer = io.StringIO()
    transport = StdioTransport(reader=reader, writer=writer)
    await transport.serve(_echo_handler())
    out = writer.getvalue().strip()
    payload = json.loads(out)
    assert payload["id"] == 1
    assert payload["result"]["method"] == "echo"


async def test_stdio_emits_parse_error_for_garbage_line() -> None:
    reader = io.StringIO("not-json\n")
    writer = io.StringIO()
    transport = StdioTransport(reader=reader, writer=writer)
    await transport.serve(_echo_handler())
    out = writer.getvalue().strip()
    payload = json.loads(out)
    assert payload["error"]["code"] == -32700


async def test_stdio_drops_notifications_silently() -> None:
    reader = io.StringIO('{"jsonrpc":"2.0","method":"notify"}\n')
    writer = io.StringIO()
    transport = StdioTransport(reader=reader, writer=writer)
    await transport.serve(_echo_handler())
    assert writer.getvalue() == ""


def test_loopback_http_refuses_non_loopback() -> None:
    with pytest.raises(ValueError):
        LoopbackHttpTransport(port=8765, host="10.0.0.5")


def test_loopback_http_refuses_invalid_port() -> None:
    with pytest.raises(ValueError):
        LoopbackHttpTransport(port=0)
    with pytest.raises(ValueError):
        LoopbackHttpTransport(port=70000)


@pytest.mark.slow
async def test_loopback_http_round_trip() -> None:
    """End-to-end loopback HTTP round trip — gated behind the slow marker
    because it opens a real listening socket and pytest's
    unraisableexception hook flags any GC-finalized sockets as test
    failures. Re-enabled via `make test-full`.
    """

    port = _free_loopback_port()
    transport = LoopbackHttpTransport(port=port)

    server_task = asyncio.create_task(transport.serve(_echo_handler()))
    try:
        await asyncio.sleep(0.05)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        body = b'{"jsonrpc":"2.0","id":42,"method":"echo"}'
        request = (
            b"POST / HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
            b"Connection: close\r\n\r\n" + body
        )
        writer.write(request)
        await writer.drain()
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
    finally:
        await transport.stop()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

    _headers, _, body_bytes = raw.partition(b"\r\n\r\n")
    payload = json.loads(body_bytes.decode("utf-8"))
    assert payload["id"] == 42


def test_loopback_http_accessor_properties() -> None:
    transport = LoopbackHttpTransport(port=12345)
    assert transport.host == "127.0.0.1"
    assert transport.port == 12345


async def test_loopback_http_handle_body_round_trip() -> None:
    transport = LoopbackHttpTransport(port=12345)
    transport._handle_request = _echo_handler()
    response = await transport._handle_http_body(b'{"jsonrpc":"2.0","id":7,"method":"echo"}')
    assert response["id"] == 7


async def test_loopback_http_handle_body_returns_parse_error_for_garbage() -> None:
    transport = LoopbackHttpTransport(port=12345)
    transport._handle_request = _echo_handler()
    response = await transport._handle_http_body(b"not-json")
    assert response["error"]["code"] == -32700


async def test_loopback_http_handle_body_notification_returns_null_result() -> None:
    transport = LoopbackHttpTransport(port=12345)
    transport._handle_request = _echo_handler()
    response = await transport._handle_http_body(b'{"jsonrpc":"2.0","method":"notify"}')
    assert response == {"jsonrpc": "2.0", "id": None, "result": None}


def test_wire_parse_error_truncates_fragment() -> None:
    payload = _wire_parse_error("x" * 500, ValueError("bad"))
    assert payload["error"]["code"] == -32700
    assert len(payload["error"]["data"]["fragment"]) <= 120


async def test_read_http_request_handles_non_post() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    reader.feed_eof()
    body = await _read_http_request(reader)
    assert body == b""


async def test_read_http_request_handles_zero_length() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"POST / HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
    reader.feed_eof()
    body = await _read_http_request(reader)
    assert body == b""


async def test_read_http_request_reads_body_by_length() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(
        b"POST / HTTP/1.1\r\nContent-Length: 5\r\nContent-Type: application/json\r\n\r\nhello"
    )
    reader.feed_eof()
    body = await _read_http_request(reader)
    assert body == b"hello"


async def test_handle_connection_round_trip_via_fake_streams() -> None:
    """Drive ``_handle_connection`` end-to-end without a real socket.

    Uses an in-memory ``StreamReader`` for the request and a recording
    ``StreamWriter`` for the response. Exercises the full
    request-parse → body-handler → response-write path.
    """

    transport = LoopbackHttpTransport(port=12345)
    transport._handle_request = _echo_handler()

    body = b'{"jsonrpc":"2.0","id":99,"method":"echo"}'
    request = (
        b"POST / HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
        b"Connection: close\r\n\r\n" + body
    )
    reader = asyncio.StreamReader()
    reader.feed_data(request)
    reader.feed_eof()

    class FakeWriter:
        def __init__(self) -> None:
            self.chunks: list[bytes] = []
            self.closed = False

        def write(self, data: bytes) -> None:
            self.chunks.append(data)

        async def drain(self) -> None:
            return None

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            return None

    writer = FakeWriter()
    await transport._handle_connection(reader, writer)  # type: ignore[arg-type]
    assert writer.closed is True
    raw = b"".join(writer.chunks)
    _headers, _, body_bytes = raw.partition(b"\r\n\r\n")
    payload = json.loads(body_bytes.decode("utf-8"))
    assert payload["id"] == 99


async def test_write_http_response_emits_headers_and_body() -> None:
    """``_write_http_response`` writes a complete HTTP/1.1 response."""

    class FakeWriter:
        def __init__(self) -> None:
            self.chunks: list[bytes] = []

        def write(self, data: bytes) -> None:
            self.chunks.append(data)

        async def drain(self) -> None:
            return None

    writer = FakeWriter()
    await _write_http_response(writer, {"ok": True})  # type: ignore[arg-type]
    combined = b"".join(writer.chunks)
    assert combined.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b"Content-Type: application/json\r\n" in combined
    assert combined.endswith(b'{"ok":true}')


def _free_loopback_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
