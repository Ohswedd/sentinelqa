"""Unit tests for :func:`engine.discovery.api_detector.template_path`."""

from __future__ import annotations

import pytest
from engine.discovery.api_detector import template_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/api/users", "/api/users"),
        ("/api/users/", "/api/users/"),
        ("/api/users/123", "/api/users/[id]"),
        ("/api/users/123/posts", "/api/users/[id]/posts"),
        ("/api/users/123/posts/45", "/api/users/[id]/posts/[id]"),
        (
            "/api/items/550e8400-e29b-41d4-a716-446655440000",
            "/api/items/[uuid]",
        ),
        ("/api/items/AAAAAAAAAAAAAAAA0123", "/api/items/[hex]"),
        ("/api/items/AAAAAAAAAAAAAAAA0123?q=1", "/api/items/[hex]?q=1"),
        ("/api/users/john-doe", "/api/users/john-doe"),
    ],
)
def test_template_path(raw: str, expected: str) -> None:
    assert template_path(raw) == expected


def test_root_path_preserved() -> None:
    assert template_path("/") == "/"
