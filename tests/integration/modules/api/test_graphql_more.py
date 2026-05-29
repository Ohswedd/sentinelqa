"""Coverage for less-trodden contract_graphql branches."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig

from modules.api.checks.contract_graphql import run_graphql_contract_check
from modules.api.graphql import load_graphql


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(graphql_endpoint="/graphql"),
    )


def test_graphql_invalid_json_response_flagged(
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text("type Query { ok: Boolean }", encoding="utf-8")
    schema = load_graphql(sdl_path)
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, headers={"Content-Type": "application/json"}, content=b"not json"
        )
    )
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    finally:
        client.close()
    assert any(i.rule_id == "GRAPHQL-INVALID-JSON" for i in result.issues)


def test_graphql_non_object_body_flagged(
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text("type Query { ok: Boolean }", encoding="utf-8")
    schema = load_graphql(sdl_path)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=["not", "an", "object"]))
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    finally:
        client.close()
    assert any(i.rule_id == "GRAPHQL-SHAPE" for i in result.issues)
