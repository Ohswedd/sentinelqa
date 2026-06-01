"""Deterministic planner core (task 06.01, the documentation).

Given a :class:`DiscoveryGraph` and a :class:`RiskMap`, the planner emits a
:class:`TestPlan` enumerating every flow and the test types it requires.

Rules (audited, in the order applied):

1. Every route in the graph gets a smoke flow that asserts a successful
   page load and a stable anchor element.
2. Every form gets a functional flow (P1 by default; P0 if the route looks
   like login / signup / payment / admin).
3. Every form whose ``submit_handler_present`` is ``False`` is flagged as
   an ``LlmAuditCandidate`` — its smoke flow gains the ``llm_audit_candidate``
   tag so Phase 19 can pick it up.
4. Every API endpoint gets a contract test case (Phase 22 will execute it).
5. Every auth-required route gets an auth-boundary functional flow.

Confidence is fixed at 0.95 for deterministic flows (LLM-sourced flows
get whatever the adapter returned; merging happens in
``engine.planner.merge`` once the LLM adapter ships).

Determinism contract: the same ``(DiscoveryGraph, RiskMap, RootConfig)``
triple always produces the same plan modulo IDs. Tests that need
byte-stable output inject an :class:`IdGenerator` whose ``_random_slug``
is monkey-patched to a counting function.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from engine.config.schema import RootConfig
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow, FlowStep, Priority, Risk
from engine.domain.form import Form
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap
from engine.domain.route import Route
from engine.domain.test_case import TestCase, TestType
from engine.domain.test_plan import CoverageEstimate, TestPlan
from engine.planner.flows import FlowExtractor, builtin_extractors, run_extractors

DETERMINISTIC_CONFIDENCE: float = 0.95
"""Confidence stamp every deterministic flow carries (the documentation)."""

_PRIORITY_BY_RISK: Mapping[Risk, Priority] = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}

# Risk-bucket cutoffs applied to RouteRisk.score (∈ [0.0, 1.0]).
_RISK_BUCKETS: tuple[tuple[float, Risk], ...] = (
    (0.80, "critical"),
    (0.60, "high"),
    (0.30, "medium"),
)
_DEFAULT_RISK: Risk = "low"

# Path-substring → flow kind. The matchers are intentionally simple and
# audited; the LLM adapter (Phase 06.04) can override or extend later.
_LOGIN_HINTS: tuple[str, ...] = ("/login", "/sign-in", "/signin", "/log-in")
_SIGNUP_HINTS: tuple[str, ...] = ("/signup", "/sign-up", "/register", "/create-account")
_PAYMENT_HINTS: tuple[str, ...] = (
    "/checkout",
    "/payment",
    "/pay",
    "/billing",
    "/subscribe",
)
_ADMIN_HINTS: tuple[str, ...] = ("/admin", "/manage", "/console", "/superuser")


def bucketed_risk(score: float) -> Risk:
    """Map a ``RouteRisk.score`` (0..1) to the named risk bucket."""

    for threshold, label in _RISK_BUCKETS:
        if score >= threshold:
            return label
    return _DEFAULT_RISK


def priority_for_risk(risk: Risk) -> Priority:
    """Return the canonical priority for the given risk bucket."""

    return _PRIORITY_BY_RISK[risk]


def _has_any(path: str, needles: Iterable[str]) -> bool:
    lowered = path.lower()
    return any(needle in lowered for needle in needles)


def _classify_route(route: Route) -> str:
    """Return a short tag for sensitive routes (used for priority bumps)."""

    if _has_any(route.path, _LOGIN_HINTS):
        return "login"
    if _has_any(route.path, _SIGNUP_HINTS):
        return "signup"
    if _has_any(route.path, _PAYMENT_HINTS):
        return "payment"
    if _has_any(route.path, _ADMIN_HINTS):
        return "admin"
    return ""


def _bump_for_sensitive(category: str, base: Priority) -> Priority:
    """Raise priority to P0 for login/payment/admin/signup routes."""

    if category in {"login", "payment", "admin", "signup"} and base != "P0":
        return "P0"
    return base


@dataclass(frozen=True)
class PlanningOutcome:
    """Structured output of :meth:`DeterministicPlanner.plan`.

    Aside from the canonical :class:`TestPlan`, holds the in-memory mapping
    from flow → test cases so downstream consumers (writer, generator) can
    cross-reference without re-traversing the plan.
    """

    plan: TestPlan
    flows_by_route_id: Mapping[str, tuple[Flow, ...]]


class DeterministicPlanner:
    """Stateless deterministic planner."""

    def __init__(
        self,
        *,
        id_generator: IdGenerator | None = None,
        extractors: tuple[FlowExtractor, ...] | None = None,
    ) -> None:
        self._ids = id_generator or IdGenerator()
        self._extractors = extractors if extractors is not None else builtin_extractors()

    def plan(
        self,
        graph: DiscoveryGraph,
        risk: RiskMap,
        config: RootConfig,
        *,
        run_id: str,
    ) -> PlanningOutcome:
        """Produce a :class:`TestPlan` from the supplied graph + risk map."""

        risk_score_by_route: dict[str, float] = {
            entry.route_id: entry.score for entry in risk.entries
        }
        auth_required_route_ids: frozenset[str] = frozenset(
            route.id for route in graph.routes if route.auth_required
        )
        form_routes_without_handler: dict[str, list[Form]] = {}
        # Forms aren't linked to routes by domain model yet; we attach them
        # heuristically by URL host+path matching the route path. Until
        # discovery surfaces the link directly, we bucket all forms under
        # the first matching route (or skip if none).
        forms_by_route: dict[str, list[Form]] = _bucket_forms_by_route(graph.routes, graph.forms)

        flows_acc: list[Flow] = []
        cases_acc: list[TestCase] = []
        flows_by_route: dict[str, list[Flow]] = {}

        # Sort routes by path for deterministic iteration order. Within the
        # plan, ordering is by (priority, risk, path).
        sorted_routes = sorted(graph.routes, key=lambda r: (r.path, r.id))

        for route in sorted_routes:
            risk_bucket = bucketed_risk(risk_score_by_route.get(route.id, 0.0))
            category = _classify_route(route)
            base_priority = _bump_for_sensitive(category, priority_for_risk(risk_bucket))

            # Rule 1: smoke flow per route.
            tags: list[str] = ["smoke"]
            if category:
                tags.append(f"category:{category}")

            route_forms = forms_by_route.get(route.id, [])
            forms_without_handler = [f for f in route_forms if not f.submit_handler_present]
            if forms_without_handler:
                tags.append("llm_audit_candidate")
                form_routes_without_handler[route.id] = forms_without_handler

            smoke_flow = self._make_flow(
                name=f"smoke: {route.path}",
                description=(f"Smoke test: load {route.path} and assert a stable anchor element."),
                steps=(
                    FlowStep(
                        description=f"Navigate to {route.path}",
                        target_route_id=route.id,
                        expected_outcome="page renders without 5xx errors",
                    ),
                    FlowStep(
                        description="Assert an anchor element is visible",
                        target_route_id=route.id,
                        expected_outcome="anchor element is present in the rendered DOM",
                    ),
                ),
                priority=base_priority,
                risk=risk_bucket,
                extractor="route.smoke",
                tags=tags,
            )
            flows_acc.append(smoke_flow)
            flows_by_route.setdefault(route.id, []).append(smoke_flow)
            cases_acc.append(self._make_case(smoke_flow, test_type="functional"))

            # Rule 5: auth-boundary functional flow for protected routes.
            if route.id in auth_required_route_ids:
                ab_flow = self._make_flow(
                    name=f"auth-boundary: {route.path}",
                    description=(
                        "Anonymous request must be redirected or 401; authenticated "
                        "request must succeed."
                    ),
                    steps=(
                        FlowStep(
                            description=f"Anonymous GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="redirect to login OR 401/403 response",
                        ),
                        FlowStep(
                            description=f"Authenticated GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="200 response with authenticated content",
                        ),
                    ),
                    priority=_bump_for_sensitive("admin", base_priority)
                    if category == "admin"
                    else base_priority,
                    risk=risk_bucket,
                    required_auth_role=self._role_for_route(route.id, graph),
                    extractor="route.auth_boundary",
                    tags=["auth_boundary", "security"],
                )
                flows_acc.append(ab_flow)
                flows_by_route.setdefault(route.id, []).append(ab_flow)
                cases_acc.append(self._make_case(ab_flow, test_type="functional"))

            # Rule 2 + 3: every form → functional flow; if no submit handler,
            # tag llm_audit_candidate.
            for form in route_forms:
                form_priority: Priority = (
                    "P0" if category in {"login", "payment", "admin", "signup"} else "P1"
                )
                if base_priority == "P0":  # if route already P0 by risk, take the higher of the two
                    form_priority = "P0"
                form_tags = ["form", f"form:{form.id}"]
                if category:
                    form_tags.append(f"category:{category}")
                test_type: TestType = "functional"
                if not form.submit_handler_present:
                    form_tags.append("llm_audit_candidate")
                    test_type = "llm_audit"
                form_flow = self._make_flow(
                    name=f"submit form on {route.path}",
                    description=(
                        f"Fill the form ({len(form.fields)} field(s)) and verify "
                        "submission outcome."
                    ),
                    steps=(
                        FlowStep(
                            description=f"Navigate to {route.path}",
                            target_route_id=route.id,
                            expected_outcome="form is present and interactive",
                        ),
                        FlowStep(
                            description="Fill required fields with safe sample data",
                            target_route_id=route.id,
                            expected_outcome="all required fields accept input",
                        ),
                        FlowStep(
                            description="Submit the form",
                            target_route_id=route.id,
                            expected_outcome=(
                                "server returns a success or validated-failure response"
                            ),
                        ),
                    ),
                    priority=form_priority,
                    risk=risk_bucket,
                    required_auth_role=self._role_for_route(route.id, graph),
                    extractor="form.submit",
                    tags=form_tags,
                )
                flows_acc.append(form_flow)
                flows_by_route.setdefault(route.id, []).append(form_flow)
                cases_acc.append(self._make_case(form_flow, test_type=test_type))

        # Rule 6: run named extractors (login/signup/CRUD/admin/role/etc.).
        extractor_flows = run_extractors(self._extractors, graph, id_generator=self._ids)
        for ext_flow in extractor_flows:
            flows_acc.append(ext_flow)
            # Attach a TestCase per extractor flow. Test type is picked from
            # the extractor's domain so the runner routes correctly.
            cases_acc.append(
                self._make_case(ext_flow, test_type=_test_type_for_extractor(ext_flow.extractor))
            )

        # Rule 4: every API endpoint → contract test case. We hang each one
        # off a synthetic flow (one per endpoint) so the case has a flow_id.
        for endpoint in _sorted_endpoints(graph.api_endpoints):
            api_flow = self._make_flow(
                name=f"api contract: {endpoint.method} {endpoint.path}",
                description=(
                    f"Contract test for {endpoint.method} {endpoint.path} "
                    f"(source={endpoint.source})."
                ),
                steps=(
                    FlowStep(
                        description=f"Issue {endpoint.method} {endpoint.path}",
                        expected_outcome="response matches the documented contract",
                    ),
                ),
                priority="P1",
                risk="high" if endpoint.auth_strategy != "none" else "medium",
                extractor="api.contract",
                tags=("api", f"endpoint:{endpoint.id}", f"source:{endpoint.source}"),
            )
            flows_acc.append(api_flow)
            cases_acc.append(self._make_case(api_flow, test_type="api"))

        # Stable order: (priority asc, risk severity desc, name)
        ordered_flows = tuple(
            sorted(flows_acc, key=lambda f: (f.priority, -_risk_weight(f.risk), f.name, f.id))
        )
        # Test cases keep their flow's relative ordering.
        flow_index_by_id = {flow.id: idx for idx, flow in enumerate(ordered_flows)}
        ordered_cases = tuple(
            sorted(
                cases_acc,
                key=lambda c: (flow_index_by_id.get(c.flow_id, 1 << 30), c.test_type, c.id),
            )
        )

        coverage = _coverage_estimate(ordered_cases)

        plan = TestPlan(
            id=self._ids.new("PLN"),
            run_id=run_id,
            discovery_graph_id=graph.id,
            risk_map_id=risk.id,
            target_url=str(config.target.base_url),
            flows=ordered_flows,
            test_cases=ordered_cases,
            coverage_estimate=coverage,
        )
        return PlanningOutcome(
            plan=plan,
            flows_by_route_id={k: tuple(v) for k, v in flows_by_route.items()},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_flow(
        self,
        *,
        name: str,
        description: str,
        steps: tuple[FlowStep, ...],
        priority: Priority,
        risk: Risk,
        extractor: str,
        tags: Iterable[str],
        required_auth_role: str | None = None,
        required_data_state: str | None = None,
        confidence: float = DETERMINISTIC_CONFIDENCE,
    ) -> Flow:
        return Flow(
            id=self._ids.new("FLW"),
            name=name,
            description=description,
            steps=steps,
            priority=priority,
            risk=risk,
            confidence=confidence,
            required_auth_role=required_auth_role,
            required_data_state=required_data_state,
            extractor=extractor,
            source="deterministic",
            tags=tuple(tags),
        )

    def _make_case(self, flow: Flow, *, test_type: TestType) -> TestCase:
        # Phase 06 emits relative spec paths under tests/sentinel/. The
        # generator (Phase 07) will overwrite the file path when it writes
        # the actual file; we use a deterministic placeholder so plan.json
        # round-trips cleanly. Pydantic 2's Path validator rejects
        # PurePosixPath, so we use Path explicitly with forward slashes —
        # that keeps the on-disk JSON stable across OSes.
        from pathlib import Path

        slug = _slug_from_id(flow.id)
        file_path = Path(f"tests/sentinel/{test_type}_{slug}.spec.ts")
        return TestCase(
            id=self._ids.new("TC"),
            flow_id=flow.id,
            file_path=file_path,
            test_type=test_type,
            confidence=flow.confidence,
        )

    @staticmethod
    def _role_for_route(route_id: str, graph: DiscoveryGraph) -> str | None:
        for boundary in graph.auth_boundaries:
            if boundary.route_id == route_id:
                return boundary.required_role
        return None


# ----------------------------------------------------------------------
# Module-internal helpers
# ----------------------------------------------------------------------


def _risk_weight(risk: Risk) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}[risk]


def _slug_from_id(value: str) -> str:
    # Convert FLW-XXXXX → flw_xxxxx (lower, dash → underscore) for use in
    # file names so PurePosixPath remains deterministic and shell-safe.
    return value.lower().replace("-", "_")


def _sorted_endpoints(endpoints: tuple[ApiEndpoint, ...]) -> tuple[ApiEndpoint, ...]:
    return tuple(sorted(endpoints, key=lambda e: (e.path, e.method, e.id)))


def _coverage_estimate(cases: tuple[TestCase, ...]) -> CoverageEstimate:
    counts: dict[str, int] = {}
    for case in cases:
        key = case.module or case.test_type
        # `regression` falls back to `functional` via the TestCase validator.
        counts[key] = counts.get(key, 0) + 1
    return CoverageEstimate(by_module=dict(sorted(counts.items())), total=len(cases))


_EXTRACTOR_TO_TEST_TYPE: Mapping[str, TestType] = {
    "login": "functional",
    "signup": "functional",
    "logout": "functional",
    "password_reset": "functional",
    "crud": "functional",
    "search_filter_sort": "functional",
    "admin": "functional",
    "role": "functional",
    "file_upload_download": "functional",
    "payment_sandbox": "functional",
    "notification": "functional",
}


def _test_type_for_extractor(extractor: str) -> TestType:
    return _EXTRACTOR_TO_TEST_TYPE.get(extractor, "functional")


def _bucket_forms_by_route(
    routes: tuple[Route, ...],
    forms: tuple[Form, ...],
) -> dict[str, list[Form]]:
    """Heuristically attach every form to a route.

    Until discovery surfaces an explicit form→route link, we match forms
    whose ``action_url`` path matches a route path. Forms with no action
    URL are bucketed to the first route (sorted by path). The result is
    deterministic for a given input.
    """

    if not forms:
        return {}
    if not routes:
        return {}
    routes_by_path: dict[str, Route] = {}
    for route in sorted(routes, key=lambda r: r.path):
        routes_by_path.setdefault(route.path, route)
    default_route = sorted(routes, key=lambda r: r.path)[0]

    out: dict[str, list[Form]] = {}
    for form in sorted(forms, key=lambda f: f.id):
        target_path: str | None = None
        if form.action_url is not None:
            target_path = form.action_url.path or "/"
        route = routes_by_path.get(target_path or "", default_route)
        out.setdefault(route.id, []).append(form)
    return out


__all__ = [
    "DETERMINISTIC_CONFIDENCE",
    "DeterministicPlanner",
    "PlanningOutcome",
    "bucketed_risk",
    "priority_for_risk",
]
