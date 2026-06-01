"""End-to-end coverage of ApiModule.run against an httpserver fixture.

Hits the dispatch branches in ``modules.api.module._run_audit`` that
unit tests of individual checks cannot reach (OpenAPI + GraphQL
loaded, backward-compat snapshot persisted, audit log written, etc.).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from engine.config.schema import ApiConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl
from pytest_httpserver import HTTPServer

from modules.api.backward_compat import write_snapshot
from modules.api.models import (
    API_SCHEMA_SNAPSHOT_VERSION,
    ApiSchemaEndpoint,
    ApiSchemaSnapshot,
)
from modules.api.module import ApiModule


def _spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/users": {
                "post": {
                    "operationId": "create_user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email"],
                                    "properties": {"email": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }


@pytest.fixture
def httpserver_url(httpserver: HTTPServer) -> str:
    # Default catch-all so every probe gets *something* without crashing.
    httpserver.expect_request("/items", method="GET").respond_with_json([], status=200)
    httpserver.expect_request("/users", method="POST").respond_with_data(
        '{"error":"bad"}', status=400, content_type="application/json"
    )
    return str(httpserver.url_for(""))


def _root_config(url: str, openapi_path: Path) -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl(url), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(openapi_path=openapi_path),
    )


def _ctx(
    tmp_path: Path,
    config: RootConfig,
    options: dict[str, Any] | None = None,
) -> ModuleContext:
    artifacts = ArtifactDirectory.create(tmp_path / "runs", run_id="RUN-E2EAPIABCDEF")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode="safe",
    )
    return ModuleContext(
        module_name="api",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="fixture",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-E2EAPIABCDEF",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": options or {}},
    )


def test_full_run_with_openapi_doc_writes_snapshot(
    httpserver_url: str,
    tmp_path: Path,
) -> None:
    openapi_path = tmp_path / "openapi.json"
    openapi_path.write_text(json.dumps(_spec()), encoding="utf-8")
    config = _root_config(httpserver_url, openapi_path)
    ctx = _ctx(tmp_path, config)
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    # api-schema.json must be persisted so subsequent runs can diff against it.
    assert (ctx.run_dir / "api" / "api-schema.json").exists()
    # The contract check ran (openapi_loaded must be 1).
    assert result.metrics["openapi_loaded"] == 1


def test_run_with_explicit_diff_since_picks_prior_snapshot(
    httpserver_url: str,
    tmp_path: Path,
) -> None:
    # Create a prior snapshot in a sibling RUN dir under <tmp>/runs/.
    runs_root = tmp_path / "runs"
    prev_dir = runs_root / "RUN-PRIOR-AAAAAAA1" / "api"
    prev_dir.mkdir(parents=True, exist_ok=True)
    write_snapshot(
        prev_dir / "api-schema.json",
        ApiSchemaSnapshot(
            schema_version=API_SCHEMA_SNAPSHOT_VERSION,
            source="openapi",
            endpoints=(
                ApiSchemaEndpoint(
                    method="GET",
                    path="/removed",
                    required_response_fields=(),
                    response_status_codes=(200,),
                    required_request_fields=(),
                    response_field_types=(),
                ),
            ),
        ),
    )

    openapi_path = tmp_path / "openapi.json"
    openapi_path.write_text(json.dumps(_spec()), encoding="utf-8")
    config = _root_config(httpserver_url, openapi_path)
    ctx = _ctx(
        tmp_path,
        config,
        options={
            "diff_since_run_id": "RUN-PRIOR-AAAAAAA1",
            "artifacts_root": runs_root,
        },
    )
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    # The backward-compat check should have raised at least one finding.
    bc_findings = [f for f in result.findings if f.category.startswith("api/backward_compat/")]
    assert bc_findings, [f.category for f in result.findings]


def test_run_with_graphql_doc_persists_graphql_snapshot(
    httpserver_url: str,
    tmp_path: Path,
    httpserver: HTTPServer,
) -> None:
    sdl_path = tmp_path / "schema.graphql"
    sdl_path.write_text("type Query { ok: Boolean }", encoding="utf-8")
    httpserver.expect_request("/graphql", method="POST").respond_with_json({"data": {"ok": True}})
    config = RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl(httpserver_url), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(graphql_path=sdl_path),
    )
    artifacts = ArtifactDirectory.create(tmp_path / "runs", run_id="RUN-GQLAPIABCDEF")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset({"127.0.0.1"}),
        mode="safe",
    )
    ctx = ModuleContext(
        module_name="api",
        config=config,
        safety_decision=SafetyDecision(
            allowed=True,
            reason="fixture",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-GQLAPIABCDEF",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": {}},
    )
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    snapshot_path = ctx.run_dir / "api" / "api-schema.json"
    assert snapshot_path.exists()
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snap["source"] == "graphql"
    assert result.metrics["graphql_loaded"] == 1


def test_invalid_openapi_doc_path_logs_skip(
    httpserver_url: str,
    tmp_path: Path,
) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not json", encoding="utf-8")
    config = _root_config(httpserver_url, bad_path)
    ctx = _ctx(tmp_path, config)
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    # The contract check must record a skip with the load error.
    api_index = json.loads((ctx.run_dir / "api" / "index.json").read_text(encoding="utf-8"))
    contract_results = [c for c in api_index["checks"] if c["check"] == "contract"]
    assert any(c["skipped"] for c in contract_results)
    assert result.name == "api"
