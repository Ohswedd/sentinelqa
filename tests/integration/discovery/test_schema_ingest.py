"""Integration tests for OpenAPI + GraphQL ingestion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from engine.discovery.graphql_ingest import GraphQLIngester
from engine.discovery.openapi_ingest import OpenAPIIngester
from pytest_httpserver import HTTPServer


def test_openapi_ingest_from_file(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.3",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/api/users": {
                        "get": {
                            "responses": {
                                "200": {
                                    "description": "ok",
                                    "content": {"application/json": {"schema": {"type": "array"}}},
                                }
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    result = OpenAPIIngester().ingest(path=spec_path)
    assert result.title == "T"
    assert result.version == "1"
    assert len(result.endpoints) == 1
    assert result.endpoints[0].source == "openapi"
    assert result.endpoints[0].path == "/api/users"


def test_openapi_ingest_from_url(
    discovery_server: HTTPServer,
    discovery_base_url: str,
) -> None:
    result = OpenAPIIngester().ingest(url=discovery_server.url_for("/openapi.json"))
    assert result.title == "Test API"
    assert result.version == "1.2.3"
    paths = {ep.path for ep in result.endpoints}
    assert paths == {"/api/users", "/api/items/{id}", "/api/orphan"}


def test_openapi_cross_check_flags_undocumented_and_expected() -> None:
    from engine.domain.api_endpoint import ApiEndpoint

    ingested = (
        ApiEndpoint(
            id="API-AAAAAAAAAAAA",
            method="GET",
            path="/api/users",
            source="openapi",
        ),
    )
    observed = (
        ApiEndpoint(
            id="API-BBBBBBBBBBBB",
            method="GET",
            path="/api/users",
            source="discovered",
        ),
        ApiEndpoint(
            id="API-CCCCCCCCCCCC",
            method="GET",
            path="/api/secret",
            source="discovered",
        ),
    )
    cross = OpenAPIIngester().cross_check(ingested=ingested, observed=observed)
    assert cross.undocumented_paths == ("/api/secret",)
    assert cross.expected_but_not_observed == ()


def test_graphql_ingest_from_sdl(tmp_path: Path) -> None:
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text(
        """
        type Query {
          users: [String!]!
          me: String
        }
        type Mutation {
          createUser(name: String!): String
        }
        """,
        encoding="utf-8",
    )
    result = GraphQLIngester().ingest_sdl(sdl_path, endpoint_url="/graphql")
    paths = {ep.path for ep in result.endpoints}
    assert paths == {
        "/graphql#query.users",
        "/graphql#query.me",
        "/graphql#mutation.createUser",
    }
    assert all(ep.source == "graphql" for ep in result.endpoints)


def test_openapi_url_rejects_non_http(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        OpenAPIIngester().ingest(url="file:///etc/passwd")
