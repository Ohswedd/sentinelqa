"""Shared fixtures for engine.llm.providers unit tests.

Every provider is exercised against an in-memory ``httpx.MockTransport``
that returns canned responses. The MockTransport pattern keeps tests
hermetic and lets us assert on the request body / headers that the
adapter built.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest


def make_mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """Return an httpx.Client backed by a MockTransport."""

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def make_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.Client]:
    return make_mock_client


def assert_json_body(request: httpx.Request) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(request.content.decode("utf-8"))
    return body


@pytest.fixture
def captured_requests() -> list[httpx.Request]:
    """Mutable list test code can append to so handlers can record."""

    return []


def make_handler(
    *,
    response: dict[str, Any] | None = None,
    status_code: int = 200,
    text: str | None = None,
    captured: list[httpx.Request] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Build a one-shot handler returning ``response`` JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        if text is not None:
            return httpx.Response(status_code, text=text)
        return httpx.Response(status_code, json=response or {})

    return handler


@pytest.fixture
def make_response_handler() -> Callable[..., Callable[[httpx.Request], httpx.Response]]:
    return make_handler
