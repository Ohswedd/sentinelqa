"""Unit coverage for :mod:`modules.api.http_client`."""

from __future__ import annotations

import httpx
import pytest

from modules.api.http_client import (
    ABSOLUTE_MAX_REQUEST_BYTES,
    USER_AGENT,
    RequestTooLargeError,
    TokenBucket,
    build_client,
    safe_request,
)


def test_user_agent_string_is_branded() -> None:
    assert "SentinelQA" in USER_AGENT
    assert "+https://sentinelqa.dev" in USER_AGENT


def test_build_client_sets_branded_headers() -> None:
    client = build_client(base_url="http://127.0.0.1:1", run_id="RUN-ABC", timeout_seconds=1.0)
    assert client.headers["User-Agent"] == USER_AGENT
    assert client.headers["X-SentinelQA-Test-Run"] == "RUN-ABC"
    client.close()


def test_token_bucket_paces_requests() -> None:
    bucket = TokenBucket(rate_per_second=20.0, capacity=1.0)
    # Two takes will require at least ~50ms; this exercises the wait path.
    bucket.take()
    bucket.take()


def test_safe_request_rejects_oversized_json_body() -> None:
    # No client needed; safe_request raises before issuing.
    client = build_client(base_url="http://127.0.0.1:1", run_id="RUN", timeout_seconds=1.0)
    try:
        with pytest.raises(RequestTooLargeError):
            safe_request(
                client,
                "POST",
                "/x",
                json_body={"a": "A" * (ABSOLUTE_MAX_REQUEST_BYTES + 1024)},
                max_body_kb=ABSOLUTE_MAX_REQUEST_BYTES // 1024 + 16,
            )
    finally:
        client.close()


def test_safe_request_clamps_max_body_kb_to_absolute() -> None:
    # Caller asks for a 1024 KB cap; safe_request must clamp to absolute.
    client = build_client(base_url="http://127.0.0.1:1", run_id="RUN", timeout_seconds=1.0)
    try:
        with pytest.raises(RequestTooLargeError):
            safe_request(
                client,
                "POST",
                "/x",
                content=b"A" * (ABSOLUTE_MAX_REQUEST_BYTES + 1),
                max_body_kb=1024,
            )
    finally:
        client.close()


def test_safe_request_sends_content_with_default_content_type() -> None:
    """Hits the success branch (small body + automatic content-type)."""

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=b"ok"))
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        response = safe_request(
            client,
            "POST",
            "/echo",
            content=b'{"hi":"there"}',
            max_body_kb=4,
        )
        assert response.status_code == 200
    finally:
        client.close()
