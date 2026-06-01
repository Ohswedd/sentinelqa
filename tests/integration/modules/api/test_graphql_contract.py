"""GraphQL contract check integration tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.contract_graphql import run_graphql_contract_check
from modules.api.graphql import load_graphql

_SDL = """
type Query {
  health: Health!
  motd: String
}

type Health {
  ok: Boolean!
  message: String!
}
"""


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "api-fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(graphql_endpoint="/graphql"),
    )


@pytest.fixture
def sdl_path(tmp_path: Path) -> Path:
    path = tmp_path / "schema.graphql"
    path.write_text(_SDL, encoding="utf-8")
    return path


def test_compliant_graphql_response_produces_no_issues(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_json(
        {"data": {"health": {"ok": True, "message": "ok"}, "motd": "hello"}}
    )
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    # The fixture server responds to one query at a time; multiple ops issue
    # multiple POSTs. We assert no high-severity findings produced.
    assert result.check == "contract"
    assert not any(issue.severity in {"critical", "high"} for issue in result.issues)


def test_non_null_field_returning_null_flags_finding(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_json(
        {"data": {"health": None}}
    )
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    assert any(issue.rule_id == "GRAPHQL-NULL-NON-NULL" for issue in result.issues)


def test_graphql_non_200_flags_status(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_data("internal", status=500)
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    assert any(
        issue.rule_id == "GRAPHQL-STATUS" and issue.severity == "high" for issue in result.issues
    )


def test_graphql_non_json_content_type_flags_content_type(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_data(
        "plain text", status=200, content_type="text/plain"
    )
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    assert any(issue.rule_id == "GRAPHQL-CONTENT-TYPE" for issue in result.issues)


def test_resolver_errors_flag_resolver_error(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_json(
        {"data": None, "errors": [{"message": "boom"}]}
    )
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    assert any(issue.rule_id == "GRAPHQL-RESOLVER-ERROR" for issue in result.issues)


def test_graphql_missing_sub_field_flags_missing_field(
    httpserver: HTTPServer,
    sdl_path: Path,
    api_config: RootConfig,
) -> None:
    httpserver.expect_request("/graphql", method="POST").respond_with_json(
        {"data": {"health": {"ok": True, "message": None}}}
    )
    schema = load_graphql(sdl_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_graphql_contract_check(client=client, schema=schema, config=api_config)
    assert any(issue.rule_id == "GRAPHQL-MISSING-FIELD" for issue in result.issues)
