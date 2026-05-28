"""Risk map builder (task 05.07).

Applies the rules in :mod:`engine.discovery.risk_model` to every route in
the discovery graph and produces a :class:`~engine.domain.risk_map.RiskMap`.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError

from engine.discovery.api_detector import ApiSuspicion
from engine.discovery.crawler import CrawlPage
from engine.discovery.dom_map import DomObservation
from engine.discovery.forms import FormObservation
from engine.discovery.risk_model import RuleContext, score_route
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.element import Element
from engine.domain.form import Form
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap, RouteRisk


def build_risk_map(
    graph: DiscoveryGraph,
    *,
    crawl_pages_by_url: dict[str, CrawlPage],
    route_url_by_id: dict[str, str],
    dom_observations: Iterable[DomObservation] = (),
    form_observations: Iterable[FormObservation] = (),
    api_suspicions: Iterable[ApiSuspicion] = (),
    forms_by_route: dict[str, tuple[Form, ...]] | None = None,
    api_endpoints_by_route: dict[str, tuple[ApiEndpoint, ...]] | None = None,
    id_generator: IdGenerator | None = None,
) -> RiskMap:
    """Apply the deterministic rule set to ``graph``."""

    ids = id_generator or IdGenerator()
    dom_by_url: dict[str, list[DomObservation]] = {}
    for dom_obs in dom_observations:
        dom_by_url.setdefault(dom_obs.route_url, []).append(dom_obs)
    form_by_url: dict[str, list[FormObservation]] = {}
    for form_obs in form_observations:
        form_by_url.setdefault(form_obs.route_url, []).append(form_obs)

    # Suspicions point at endpoint paths, not URLs. We map an endpoint path
    # to every route whose URL path matches it (so a suspicion on
    # `/api/users` lifts risk on the URL `/api/users`).
    suspicion_by_path: dict[str, list[ApiSuspicion]] = {}
    for sus in api_suspicions:
        suspicion_by_path.setdefault(sus.endpoint_path, []).append(sus)

    elements_by_route: dict[str, list[Element]] = {}
    for el in graph.elements:
        elements_by_route.setdefault(el.route_id, []).append(el)

    entries: list[RouteRisk] = []
    for route in graph.routes:
        url = route_url_by_id.get(route.id, "")
        page = crawl_pages_by_url.get(url)
        ctx = RuleContext(
            route=route,
            route_url=url,
            elements_on_route=tuple(elements_by_route.get(route.id, ())),
            forms_on_route=tuple(f.id for f in (forms_by_route or {}).get(route.id, ())),
            dom_observations_on_route=tuple(dom_by_url.get(url, ())),
            form_observations_on_route=tuple(form_by_url.get(url, ())),
            api_suspicions_on_route=tuple(suspicion_by_path.get(url, ())),
            crawl_status_code=page.status_code if page else 0,
            crawl_failed=bool(page and page.network_error),
            api_endpoints_on_route=tuple((api_endpoints_by_route or {}).get(route.id, ())),
        )
        score, justifications = score_route(ctx)
        try:
            entries.append(RouteRisk(route_id=route.id, score=score, justifications=justifications))
        except ValidationError:
            continue

    return RiskMap(id=ids.new("RM"), entries=tuple(entries))


__all__ = ["build_risk_map"]
