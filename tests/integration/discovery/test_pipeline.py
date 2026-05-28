"""End-to-end pipeline test against the fixture HTTP server."""

from __future__ import annotations

from pathlib import Path

from engine.discovery.crawler import CrawlPolicy
from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline
from engine.discovery.writer import write_discovery_artifacts
from pytest_httpserver import HTTPServer


def test_pipeline_end_to_end(
    discovery_server: HTTPServer,
    discovery_base_url: str,
    tmp_path: Path,
) -> None:
    pipeline = DiscoveryPipeline()
    result = pipeline.run(
        DiscoveryInputs(
            base_url=discovery_base_url,
            run_id="RUN-PIPEAAAAAAAA",
            policy=CrawlPolicy(max_depth=2, max_pages=20, rate_limit_rps=50),
            openapi_url=discovery_server.url_for("/openapi.json"),
        )
    )
    # Graph populated.
    assert len(result.graph.routes) > 0
    assert len(result.graph.elements) > 0
    assert len(result.graph.forms) > 0
    assert len(result.graph.api_endpoints) > 0
    # OpenAPI ingestion ran.
    assert result.openapi_result.title == "Test API"
    # Risk map exists for every route.
    assert {e.route_id for e in result.risk_map.entries} == {r.id for r in result.graph.routes}

    # Writer persists the five artifacts.
    written = write_discovery_artifacts(result=result, out_dir=tmp_path)
    for key in ("discovery", "forms", "api", "auth", "risk", "markdown"):
        assert key in written
        assert written[key].exists()
        if key != "markdown":
            assert written[key].read_text().strip().startswith("{")
        else:
            assert written[key].read_text().startswith("# Discovery report")
