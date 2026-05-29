"""Additional coverage for the ApiModule dispatch + helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.config.schema import ApiConfig, RootConfig
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pydantic import AnyUrl
from pytest_httpserver import HTTPServer

from modules.api.module import ApiModule


def _ctx(
    tmp_path: Path, config: RootConfig, *, options: dict[str, Any] | None = None
) -> ModuleContext:
    artifacts = ArtifactDirectory.create(tmp_path / "runs", run_id="RUN-MODADD-AAAA")
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
            reason="t",
            host="127.0.0.1",
            mode="safe",
            decided_at=datetime.now(UTC),
        ),
        artifacts=artifacts,
        run_id="RUN-MODADD-AAAA",
        run_dir=artifacts.root,
        target=target,
        id_generator=IdGenerator(),
        options={"api": options or {}},
    )


def test_invalid_graphql_doc_records_skip(
    httpserver: HTTPServer,
    tmp_path: Path,
) -> None:
    sdl_path = tmp_path / "schema.graphql"
    # Invalid GraphQL SDL — graphql-core raises on parse.
    sdl_path.write_text("definitely not graphql", encoding="utf-8")
    config = RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl(httpserver.url_for("")), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(graphql_path=sdl_path),
    )
    ctx = _ctx(tmp_path, config)
    module = ApiModule(config, ctx.safety_decision)
    module.run(ctx)
    api_index = json.loads((ctx.run_dir / "api" / "index.json").read_text(encoding="utf-8"))
    contract_results = [c for c in api_index["checks"] if c["check"] == "contract"]
    # The invalid SDL should register at least one skipped contract entry
    # whose reason mentions the SDL parse failure.
    skipped = [c for c in contract_results if c["skipped"]]
    assert skipped, contract_results
    assert any("GraphQL SDL" in (c.get("skip_reason") or "") for c in skipped)


def test_module_run_with_disabled_checks_yields_skipped(
    httpserver: HTTPServer,
    tmp_path: Path,
) -> None:
    """Operator can subset to no checks via CLI option; module records skipped."""

    config = RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": AnyUrl(httpserver.url_for("")), "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(enabled_checks=("contract",)),
    )
    ctx = _ctx(
        tmp_path,
        config,
        options={"enabled_checks": ["latency"]},  # intersects to empty set
    )
    module = ApiModule(config, ctx.safety_decision)
    result = module.run(ctx)
    assert result.status == "skipped"
    api_index = json.loads((ctx.run_dir / "api" / "index.json").read_text(encoding="utf-8"))
    assert api_index["checks"] == []
