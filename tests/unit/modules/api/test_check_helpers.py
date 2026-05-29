"""Targeted coverage for less-trodden branches in the check runners."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig

from modules.api.checks.auth import run_auth_check
from modules.api.checks.contract_graphql import run_graphql_contract_check
from modules.api.checks.contract_openapi import (
    _first_documented_2xx,
    _materialise_url,
    run_openapi_contract_check,
)
from modules.api.checks.negative import _materialise_url as _materialise_negative
from modules.api.checks.pagination import _materialise as _materialise_paginated
from modules.api.graphql import load_graphql
from modules.api.openapi import OpenApiOperation, load_openapi


def _basic_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(),
    )


def _op_with_path_param() -> OpenApiOperation:
    return OpenApiOperation(
        method="get",
        path="/items/{item_id}",
        operation_id="get_item",
        request_body_required=False,
        request_body_schema=None,
        request_body_content_type=None,
        response_schemas={200: {"type": "object"}},
        response_content_type={200: "application/json"},
        security_required=False,
        parameters=({"name": "item_id", "in": "path", "schema": {"type": "integer"}},),
    )


def _op_string_param() -> OpenApiOperation:
    return OpenApiOperation(
        method="get",
        path="/items/{slug}",
        operation_id="get_item_by_slug",
        request_body_required=False,
        request_body_schema=None,
        request_body_content_type=None,
        response_schemas={200: {"type": "object"}},
        response_content_type={200: "application/json"},
        security_required=False,
        parameters=({"name": "slug", "in": "path", "schema": {"type": "string"}},),
    )


def test_first_documented_2xx_picks_lowest_success_status() -> None:
    op = _op_with_path_param()
    assert _first_documented_2xx(op) == 200


def test_first_documented_2xx_returns_none_when_no_2xx() -> None:
    op = OpenApiOperation(
        method="get",
        path="/x",
        operation_id="x",
        request_body_required=False,
        request_body_schema=None,
        request_body_content_type=None,
        response_schemas={500: {"type": "object"}},
        response_content_type={500: "application/json"},
        security_required=False,
        parameters=(),
    )
    assert _first_documented_2xx(op) is None


def test_materialise_url_substitutes_integer_path_param() -> None:
    op = _op_with_path_param()
    url = _materialise_url(op)
    assert url == "/items/1"


def test_materialise_url_substitutes_string_path_param() -> None:
    op = _op_string_param()
    url = _materialise_url(op)
    assert url == "/items/sample"


def test_negative_materialise_url_substitutes_string_path() -> None:
    op = _op_string_param()
    assert _materialise_negative(op) == "/items/sample"


def test_pagination_materialise_substitutes_integer_path() -> None:
    op = _op_with_path_param()
    assert _materialise_paginated(op) == "/items/1"


def test_contract_check_handles_httpx_error_path() -> None:
    """Network failure becomes a CONTRACT-NETWORK medium finding."""

    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                }
            }
        },
    }

    def raise_error(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    transport = httpx.MockTransport(raise_error)
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        # Build a doc by writing the spec to a tmpfile.
        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(Path.cwd())  # no-op; just to keep `mp` usage explicit
            spec_path = Path("__test_spec.json")
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            try:
                doc = load_openapi(spec_path)
                result = run_openapi_contract_check(client=client, doc=doc, config=_basic_config())
            finally:
                spec_path.unlink()
        assert any(issue.rule_id == "CONTRACT-NETWORK" for issue in result.issues)
    finally:
        client.close()


def test_graphql_check_skips_mutations_silently(tmp_path: Path) -> None:
    sdl = """
    type Query {
      health: String
    }
    type Mutation {
      reset: Boolean
    }
    """
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text(sdl, encoding="utf-8")
    schema = load_graphql(sdl_path)

    # Respond only to the query so the mutation skip path is exercised.
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        if "health" in body["query"]:
            return httpx.Response(200, json={"data": {"health": "ok"}})
        # Mutation should NOT be probed.
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_graphql_contract_check(client=client, schema=schema, config=_basic_config())
    finally:
        client.close()
    # No high-severity issues — the mutation was not probed.
    assert not any(i.severity in {"critical", "high"} for i in result.issues)


def test_graphql_check_handles_httpx_error_path(tmp_path: Path) -> None:
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text("type Query { ok: Boolean }", encoding="utf-8")
    schema = load_graphql(sdl_path)

    def raise_error(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    transport = httpx.MockTransport(raise_error)
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_graphql_contract_check(client=client, schema=schema, config=_basic_config())
    finally:
        client.close()
    assert any(issue.rule_id == "GRAPHQL-NETWORK" for issue in result.issues)


def test_auth_check_swallows_httpx_error() -> None:
    """When _probe hits an HTTPError, the check records nothing for that probe."""

    spec = {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearer": []}],
        "paths": {
            "/profile": {
                "get": {
                    "operationId": "me",
                    "responses": {"200": {"description": "ok"}, "401": {"description": "no"}},
                }
            }
        },
    }
    spec_path = Path("__auth_spec.json")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    try:
        doc = load_openapi(spec_path)
    finally:
        spec_path.unlink()

    def raise_error(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    transport = httpx.MockTransport(raise_error)
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_auth_check(client=client, doc=doc, config=_basic_config(), env={})
    finally:
        client.close()
    # No findings because no probe could reach the target.
    assert result.issues == ()


def test_auth_check_with_no_doc_and_no_routes_skips() -> None:
    config = _basic_config()
    transport = httpx.MockTransport(lambda req: httpx.Response(200))
    client = httpx.Client(transport=transport, base_url="http://127.0.0.1:1", timeout=1.0)
    try:
        result = run_auth_check(client=client, doc=None, config=config, env={})
    finally:
        client.close()
    assert result.skipped is True
    assert result.skip_reason is not None
