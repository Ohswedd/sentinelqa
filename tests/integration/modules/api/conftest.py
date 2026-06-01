"""Shared fixtures for integration tests.

The API module is HTTP-driven, so integration tests spin up a
:mod:`pytest_httpserver`-backed local server (same pattern
security tests use). The server's ``url_for(path)`` is treated as the
target base URL; each test wires the OpenAPI / GraphQL doc inline.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from engine.domain.target import Target
from pydantic import AnyUrl
from pytest_httpserver import HTTPServer

from modules.api.http_client import build_client
from modules.api.module import ApiModule
from modules.api.openapi import OpenApiDocument, load_openapi


@pytest.fixture
def api_root_config() -> RootConfig:
    """Minimal RootConfig for the API module under test."""

    return RootConfig(
        project={"name": "api-fixture", "framework": "unknown", "package_manager": "unknown"},
        target={
            "base_url": AnyUrl("http://127.0.0.1:1"),
            "allowed_hosts": ("127.0.0.1",),
        },
        api=ApiConfig(),
    )


@pytest.fixture
def with_api_config(api_root_config: RootConfig) -> RootConfig:
    return api_root_config


@pytest.fixture
def write_openapi(tmp_path: Path) -> Any:
    """Return a writer that persists an OpenAPI doc to tmp_path."""

    def _write(spec: dict[str, Any]) -> Path:
        path = tmp_path / "openapi.json"
        path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_graphql(tmp_path: Path) -> Any:
    """Return a writer that persists a GraphQL SDL to tmp_path."""

    def _write(sdl: str) -> Path:
        path = tmp_path / "schema.graphql"
        path.write_text(sdl, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def fixture_httpserver(httpserver: HTTPServer) -> Iterator[HTTPServer]:
    yield httpserver


@pytest.fixture
def fixture_client(httpserver: HTTPServer) -> Iterator[httpx.Client]:
    with build_client(
        base_url=httpserver.url_for(""),
        run_id="RUN-FIXTURE",
        timeout_seconds=5.0,
    ) as client:
        yield client


@pytest.fixture
def fixture_doc_loader() -> Any:
    return load_openapi


@pytest.fixture
def fixture_module(api_root_config: RootConfig) -> ApiModule:
    from datetime import UTC, datetime

    from engine.policy.safety import SafetyDecision

    decision = SafetyDecision(
        allowed=True,
        reason="fixture",
        host="127.0.0.1",
        mode="safe",
        decided_at=datetime.now(UTC),
    )
    return ApiModule(api_root_config, decision)


@pytest.fixture
def fixture_target(httpserver: HTTPServer, api_root_config: RootConfig) -> Target:
    return Target(
        base_url=AnyUrl(httpserver.url_for("")),
        allowed_hosts=frozenset({"127.0.0.1"}),
        mode="safe",
    )


__all__ = [
    "OpenApiDocument",
]
