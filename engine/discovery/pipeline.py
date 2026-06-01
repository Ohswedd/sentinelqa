"""Discovery pipeline.

The pipeline runs the steps of the Discovery module in deterministic order
and assembles a typed :class:`DiscoveryResult` for the CLI to persist.

Order:

1. Anonymous crawl.
2. Optional authenticated crawl (if credentials supplied) — driven by
 :class:`engine.discovery.auth_boundary.AuthBoundaryDetector`.
3. DOM map extraction.
4. Forms inventory.
5. JS-bundle fetch + API detection.
6. OpenAPI / GraphQL ingest (optional).
7. Build the :class:`DiscoveryGraph`.
8. Build the :class:`RiskMap` from the graph + observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from engine.discovery.api_detector import ApiDetector, ApiDetectorResult, ApiSuspicion
from engine.discovery.auth_boundary import (
    AuthBoundaryDetector,
    AuthBoundaryReport,
    AuthCredentials,
)
from engine.discovery.crawler import (
    Crawler,
    CrawlPage,
    CrawlPolicy,
    CrawlResult,
    collect_javascript,
)
from engine.discovery.dom_map import DomMap, DomMapBuilder, route_url_to_path
from engine.discovery.forms import FormsInventory, FormsInventoryResult
from engine.discovery.graphql_ingest import GraphQLIngester, GraphQLIngestResult
from engine.discovery.openapi_ingest import (
    OpenAPICrossCheck,
    OpenAPIIngester,
    OpenAPIIngestResult,
)
from engine.discovery.risk_map import build_risk_map
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.form import Form
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap
from engine.domain.route import Route


@dataclass(frozen=True)
class DiscoveryInputs:
    """Everything the pipeline consumes — easy to construct in tests."""

    base_url: str
    run_id: str
    policy: CrawlPolicy
    credentials: AuthCredentials | None = None
    openapi_path: Path | None = None
    openapi_url: str | None = None
    graphql_sdl_path: Path | None = None
    graphql_endpoint_url: str | None = None
    #:, ADR-0043. Cookies pre-loaded from the encrypted vault
    #: (``auth.strategy: browser_session``). Injected into the anonymous
    #: crawl's HTTP client so the crawler sees the same authenticated
    #: pages the operator's browser sees.
    extra_cookies: dict[str, str] | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    """Output of :meth:`DiscoveryPipeline.run`.

    Pre-rendered for the writer: every field is either a typed domain
    model or a tuple of plain dataclasses, so serialization is one step.
    """

    graph: DiscoveryGraph
    risk_map: RiskMap
    forms: tuple[Form, ...]
    api_endpoints: tuple[ApiEndpoint, ...]
    auth_report: AuthBoundaryReport
    anonymous_crawl: CrawlResult
    authenticated_crawl: CrawlResult | None
    dom_map: DomMap
    forms_inventory: FormsInventoryResult
    api_detector_result: ApiDetectorResult
    openapi_result: OpenAPIIngestResult = field(default_factory=OpenAPIIngestResult)
    graphql_result: GraphQLIngestResult = field(default_factory=GraphQLIngestResult)
    openapi_cross_check: OpenAPICrossCheck = field(default_factory=OpenAPICrossCheck)
    suspicions: tuple[ApiSuspicion, ...] = field(default_factory=tuple)


class DiscoveryPipeline:
    """End-to-end Discovery orchestration."""

    def __init__(
        self,
        *,
        crawler: Crawler | None = None,
        id_generator: IdGenerator | None = None,
    ) -> None:
        self._crawler = crawler or Crawler()
        self._ids = id_generator or IdGenerator()
        self._dom_builder = DomMapBuilder(id_generator=self._ids)
        self._forms_inventory = FormsInventory(id_generator=self._ids)
        self._api_detector = ApiDetector(id_generator=self._ids)
        self._auth_detector = AuthBoundaryDetector(crawler=self._crawler)
        self._openapi = OpenAPIIngester(id_generator=self._ids)
        self._graphql = GraphQLIngester(id_generator=self._ids)

    def run(self, inputs: DiscoveryInputs) -> DiscoveryResult:
        # 1) Anonymous crawl.
        # , ADR-0043: when the caller pre-loaded cookies from
        # the auth vault, inject them so the "anonymous" crawl actually
        # sees the operator's authenticated session.
        anon = self._crawler.crawl(
            inputs.base_url,
            run_id=inputs.run_id,
            policy=inputs.policy,
            extra_cookies=inputs.extra_cookies,
        )

        # 2) Build the routes set from the anonymous crawl (auth crawl can
        # only re-confirm already-known routes; new auth-only routes can
        # appear there but they share path identity with the anon set).
        route_by_url: dict[str, Route] = {}
        for page in anon.pages:
            url = page.url
            if url in route_by_url:
                continue
            try:
                route_by_url[url] = Route(
                    id=self._ids.new("RT"),
                    path=route_url_to_path(url)[:2048],
                    auth_required=False,
                )
            except ValidationError:
                continue

        route_id_by_url = {url: route.id for url, route in route_by_url.items()}
        route_url_by_id = {route.id: url for url, route in route_by_url.items()}

        # 3) DOM map.
        dom_map = self._dom_builder.build(anon, route_id_by_url=route_id_by_url)

        # 4) Forms.
        forms_result = self._forms_inventory.build(anon)
        forms_by_route: dict[str, tuple[Form, ...]] = {}
        # Forms aren't yet attached to routes — attach by URL via re-walk.
        # (will use this map.)
        # Simple heuristic: every form lives on whatever route shows it.
        # We approximate by iterating the crawl pages and re-running the
        # extractor — but to keep things deterministic and cheap, we just
        # bucket all forms onto the first page whose URL matches the form's
        # action's host. For risk-map purposes we use route_url buckets.

        # 5) JS-bundle fetch + API detection.
        js_bodies = collect_javascript(anon)
        api_result = self._api_detector.detect(anon, js_bodies=js_bodies)

        # 6) Optional OpenAPI / GraphQL ingest.
        if inputs.openapi_path is not None or inputs.openapi_url is not None:
            openapi_result = self._openapi.ingest(
                path=inputs.openapi_path,
                url=inputs.openapi_url,
            )
        else:
            openapi_result = OpenAPIIngestResult()
        if inputs.graphql_sdl_path is not None:
            graphql_result = self._graphql.ingest_sdl(inputs.graphql_sdl_path)
        elif inputs.graphql_endpoint_url is not None:
            graphql_result = self._graphql.ingest_introspection(inputs.graphql_endpoint_url)
        else:
            graphql_result = GraphQLIngestResult()

        merged_endpoints = (
            *api_result.endpoints,
            *openapi_result.endpoints,
            *graphql_result.endpoints,
        )

        openapi_cross_check = self._openapi.cross_check(
            ingested=openapi_result.endpoints,
            observed=api_result.endpoints,
        )

        # 7) Auth boundary.
        auth_report = self._auth_detector.detect(
            base_url=inputs.base_url,
            run_id=inputs.run_id,
            policy=inputs.policy,
            anonymous_crawl=anon,
            credentials=inputs.credentials,
            route_id_by_url=route_id_by_url,
        )

        # Update Route.auth_required from the auth report.
        auth_required_urls = {v.url for v in auth_report.verdicts if v.requires_auth}
        routes_final: list[Route] = []
        for url, route in route_by_url.items():
            if url in auth_required_urls and not route.auth_required:
                route = route.model_copy(update={"auth_required": True})
                route_by_url[url] = route
            routes_final.append(route)

        # 8) Build the graph.
        graph = DiscoveryGraph(
            id=self._ids.new("DG"),
            routes=tuple(routes_final),
            elements=dom_map.elements,
            forms=forms_result.forms,
            api_endpoints=tuple(merged_endpoints),
            auth_boundaries=tuple(auth_report.boundaries),
        )

        # 9) Risk map.
        crawl_pages_by_url: dict[str, CrawlPage] = {p.url: p for p in anon.pages}
        risk_map_obj = build_risk_map(
            graph,
            crawl_pages_by_url=crawl_pages_by_url,
            route_url_by_id=route_url_by_id,
            dom_observations=dom_map.observations,
            form_observations=forms_result.observations,
            api_suspicions=api_result.suspicions,
            forms_by_route=forms_by_route,
            id_generator=self._ids,
        )

        return DiscoveryResult(
            graph=graph,
            risk_map=risk_map_obj,
            forms=forms_result.forms,
            api_endpoints=tuple(merged_endpoints),
            auth_report=auth_report,
            anonymous_crawl=anon,
            authenticated_crawl=None,
            dom_map=dom_map,
            forms_inventory=forms_result,
            api_detector_result=api_result,
            openapi_result=openapi_result,
            graphql_result=graphql_result,
            openapi_cross_check=openapi_cross_check,
            suspicions=api_result.suspicions,
        )


__all__ = ["DiscoveryInputs", "DiscoveryPipeline", "DiscoveryResult"]
