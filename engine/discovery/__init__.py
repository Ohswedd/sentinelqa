"""Discovery module (the documentation, Phase 05).

The discovery package builds the upstream input every other module relies on:
a :class:`~engine.domain.discovery_graph.DiscoveryGraph` (routes, elements,
forms, API endpoints, auth boundaries) and a derived
:class:`~engine.domain.risk_map.RiskMap` that lets the Planner prioritize.

ADR-0010 governs the architecture: Phase 05 ships an HTTP-first MVP backend;
the Playwright-driven backend for CSR SPAs lands in Phase 17.
"""

from __future__ import annotations

from engine.discovery.api_detector import ApiDetector, detect_api_endpoints
from engine.discovery.auth_boundary import AuthBoundaryDetector, AuthCredentials
from engine.discovery.crawler import (
    CrawlBackend,
    Crawler,
    CrawlPage,
    CrawlPolicy,
    HttpCrawlBackend,
)
from engine.discovery.dom_map import DomMapBuilder
from engine.discovery.forms import FormsInventory
from engine.discovery.graphql_ingest import GraphQLIngester
from engine.discovery.openapi_ingest import OpenAPIIngester
from engine.discovery.pipeline import DiscoveryInputs, DiscoveryPipeline, DiscoveryResult
from engine.discovery.risk_map import build_risk_map
from engine.discovery.risk_model import RISK_RULES, RiskRule

__all__ = [
    "ApiDetector",
    "AuthBoundaryDetector",
    "AuthCredentials",
    "CrawlBackend",
    "CrawlPage",
    "CrawlPolicy",
    "Crawler",
    "DiscoveryInputs",
    "DiscoveryPipeline",
    "DiscoveryResult",
    "DomMapBuilder",
    "FormsInventory",
    "GraphQLIngester",
    "HttpCrawlBackend",
    "OpenAPIIngester",
    "RISK_RULES",
    "RiskRule",
    "build_risk_map",
    "detect_api_endpoints",
]
