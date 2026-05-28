"""Flow extractors (task 06.02, PRD §9.2, §10.1).

Each extractor inspects a :class:`DiscoveryGraph` and returns zero or more
named :class:`Flow` records (e.g., login, signup, CRUD, admin). Extractors
are pure: they never mutate input, never perform I/O, and never depend on
external services. They are ordered deterministically so the planner can
merge their output reproducibly.

Confidence is the extractor's self-reported certainty (0..1). Flows below
:data:`PROPOSAL_THRESHOLD` are marked with the ``confidence_low`` tag and
should be proposed rather than executed by the runner; the deterministic
planner core uses the threshold to decide which extractor output to
forward into the plan.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow, FlowStep, Priority, Risk
from engine.domain.form import Form
from engine.domain.ids import IdGenerator
from engine.domain.route import Route

PROPOSAL_THRESHOLD: float = 0.5
"""Below this confidence, a flow is tagged ``confidence_low``."""


class FlowExtractor(Protocol):
    """Common contract for every extractor."""

    name: str

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:  # pragma: no cover - protocol stub
        ...


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _route_path_matches(route: Route, needles: Iterable[str]) -> bool:
    path = route.path.lower()
    return any(needle in path for needle in needles)


def _route_index_by_id(graph: DiscoveryGraph) -> dict[str, Route]:
    return {route.id: route for route in graph.routes}


def _form_action_route(graph: DiscoveryGraph, form: Form) -> Route | None:
    if form.action_url is None:
        return None
    target_path = form.action_url.path or "/"
    for route in graph.routes:
        if route.path == target_path:
            return route
    return None


def _form_has_field(form: Form, names: Iterable[str], *, types: Iterable[str] = ()) -> bool:
    name_set = {n.lower() for n in names}
    type_set = {t.lower() for t in types}
    for field in form.fields:
        if field.name.lower() in name_set:
            return True
        if field.type.lower() in type_set:
            return True
    return False


def _make_flow(
    *,
    id_generator: IdGenerator,
    name: str,
    description: str,
    extractor: str,
    steps: tuple[FlowStep, ...],
    priority: Priority,
    risk: Risk,
    confidence: float,
    tags: Iterable[str] = (),
    required_auth_role: str | None = None,
    required_data_state: str | None = None,
) -> Flow:
    all_tags = list(tags)
    if confidence < PROPOSAL_THRESHOLD:
        all_tags.append("confidence_low")
    all_tags.append(f"extractor:{extractor}")
    return Flow(
        id=id_generator.new("FLW"),
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
        tags=tuple(all_tags),
    )


# ----------------------------------------------------------------------
# Built-in extractors
# ----------------------------------------------------------------------


class LoginFlowExtractor:
    """Detect a login flow via path + form heuristics."""

    name = "login"
    _PATH_HINTS = ("/login", "/sign-in", "/signin", "/log-in")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        candidate_routes = [r for r in graph.routes if _route_path_matches(r, self._PATH_HINTS)]
        # Also catch any form on any route that has both an email/username
        # and a password field.
        flows: list[Flow] = []
        for form in graph.forms:
            has_password = _form_has_field(form, names=("password", "pass"), types=("password",))
            has_email = _form_has_field(
                form,
                names=("email", "username", "user", "login"),
                types=("email",),
            )
            if not (has_password and has_email):
                continue
            route = _form_action_route(graph, form) or (
                candidate_routes[0] if candidate_routes else None
            )
            confidence = 0.95 if route and _route_path_matches(route, self._PATH_HINTS) else 0.7
            flows.append(
                _make_flow(
                    id_generator=id_generator,
                    name="login",
                    description="Authenticate via the discovered login form.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Navigate to {route.path if route else '/login'}",
                            target_route_id=route.id if route else None,
                            expected_outcome="login form is visible",
                        ),
                        FlowStep(
                            description="Enter test credentials",
                            target_route_id=route.id if route else None,
                            expected_outcome="form accepts input without client-side errors",
                        ),
                        FlowStep(
                            description="Submit credentials",
                            target_route_id=route.id if route else None,
                            expected_outcome="user lands on an authenticated route",
                        ),
                    ),
                    priority="P0",
                    risk="critical",
                    confidence=confidence,
                    tags=("login", "auth"),
                )
            )
        # Edge case: login route exists but no detectable form (SPA bundle
        # didn't expose the form to the HTTP crawler).
        if not flows and candidate_routes:
            for route in candidate_routes:
                flows.append(
                    _make_flow(
                        id_generator=id_generator,
                        name="login (route-only)",
                        description=(
                            "Login route detected by path heuristic; no form found by the "
                            "HTTP crawler (SPA suspected). Phase 17 Playwright backend "
                            "is expected to fill this in."
                        ),
                        extractor=self.name,
                        steps=(
                            FlowStep(
                                description=f"Navigate to {route.path}",
                                target_route_id=route.id,
                                expected_outcome=(
                                    "route renders or redirects to authenticated landing"
                                ),
                            ),
                        ),
                        priority="P1",
                        risk="high",
                        confidence=0.45,
                        tags=("login", "auth"),
                    )
                )
        return tuple(flows)


class SignupFlowExtractor:
    name = "signup"
    _PATH_HINTS = ("/signup", "/sign-up", "/register", "/create-account", "/join")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            if not _route_path_matches(route, self._PATH_HINTS):
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name="signup",
                    description="Register a new account through the discovered signup route.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Navigate to {route.path}",
                            target_route_id=route.id,
                            expected_outcome="signup form is visible",
                        ),
                        FlowStep(
                            description="Fill required fields with safe sample data",
                            target_route_id=route.id,
                            expected_outcome="form accepts input",
                        ),
                        FlowStep(
                            description="Submit",
                            target_route_id=route.id,
                            expected_outcome=(
                                "account is created or verification email is requested"
                            ),
                        ),
                    ),
                    priority="P0",
                    risk="critical",
                    confidence=0.9,
                    tags=("signup", "auth"),
                )
            )
        return tuple(out)


class LogoutFlowExtractor:
    name = "logout"
    _PATH_HINTS = ("/logout", "/log-out", "/sign-out", "/signout")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            if not _route_path_matches(route, self._PATH_HINTS):
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name="logout",
                    description="Sign out an authenticated session.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description="Authenticate first",
                            expected_outcome="session is established",
                        ),
                        FlowStep(
                            description=f"Hit {route.path}",
                            target_route_id=route.id,
                            expected_outcome=(
                                "session cookie / token is invalidated; subsequent requests "
                                "are anonymous"
                            ),
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.9,
                    tags=("logout", "auth"),
                )
            )
        return tuple(out)


class PasswordResetFlowExtractor:
    name = "password_reset"
    _PATH_HINTS = (
        "/password-reset",
        "/reset-password",
        "/forgot-password",
        "/forgot",
        "/reset/",
    )

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            if not _route_path_matches(route, self._PATH_HINTS):
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name="password reset",
                    description="Request a password reset and follow the reset flow.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Navigate to {route.path}",
                            target_route_id=route.id,
                            expected_outcome="reset form is visible",
                        ),
                        FlowStep(
                            description="Submit email address",
                            target_route_id=route.id,
                            expected_outcome="server confirms a reset email was sent",
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.85,
                    tags=("password_reset", "auth"),
                )
            )
        return tuple(out)


class CrudFlowExtractor:
    """Detect CRUD flows from REST route shapes.

    Heuristic: any route whose path contains a templated segment (``[id]``,
    ``[uuid]``, ``[hex]`` from Phase 05's ApiDetector, OR ``:id``,
    ``{id}``) is treated as a detail/edit endpoint and the parent route is
    treated as the list endpoint. We emit one create + one read + one
    update + one delete flow per detected resource collection.
    """

    name = "crud"
    _TEMPLATE_TOKENS = ("[id]", "[uuid]", "[hex]", "/:id", "{id}")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        # Group routes by parent collection.
        collections: dict[str, list[Route]] = {}
        for route in graph.routes:
            parent = self._collection_for(route)
            if parent is None:
                continue
            collections.setdefault(parent, []).append(route)

        out: list[Flow] = []
        for parent_path in sorted(collections):
            # Look for the list route (parent_path itself or matching).
            list_route = None
            for route in graph.routes:
                if route.path == parent_path:
                    list_route = route
                    break
            # Use the first detail route as the read/edit/delete anchor.
            anchor = sorted(collections[parent_path], key=lambda r: r.path)[0]
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"crud:create {parent_path}",
                    description=(
                        f"Create a new resource under {parent_path}. "
                        "No prior fixture state required."
                    ),
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"POST {parent_path}",
                            target_route_id=list_route.id if list_route else None,
                            expected_outcome="201 with persisted entity in response",
                        ),
                    ),
                    priority="P1",
                    risk="medium",
                    confidence=0.7,
                    required_data_state="none",
                    tags=("crud", "create"),
                )
            )
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"crud:read {parent_path}",
                    description=f"Read a single resource via {anchor.path}.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"GET {anchor.path}",
                            target_route_id=anchor.id,
                            expected_outcome="200 with documented payload",
                        ),
                    ),
                    priority="P2",
                    risk="medium",
                    confidence=0.7,
                    required_data_state="existing-record",
                    tags=("crud", "read"),
                )
            )
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"crud:update {parent_path}",
                    description=f"Update a single resource via {anchor.path}.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"PATCH/PUT {anchor.path}",
                            target_route_id=anchor.id,
                            expected_outcome="200 with updated entity",
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.7,
                    required_data_state="existing-record",
                    tags=("crud", "update"),
                )
            )
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"crud:delete {parent_path}",
                    description=f"Delete a single resource via {anchor.path}.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"DELETE {anchor.path}",
                            target_route_id=anchor.id,
                            expected_outcome="204 OR 200; subsequent GET returns 404",
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.7,
                    required_data_state="existing-record",
                    tags=("crud", "delete"),
                )
            )
        return tuple(out)

    @classmethod
    def _collection_for(cls, route: Route) -> str | None:
        path = route.path
        for token in cls._TEMPLATE_TOKENS:
            if token in path:
                # Take everything up to (but not including) the templated segment.
                idx = path.find(token)
                prefix = path[:idx].rstrip("/")
                return prefix or "/"
        return None


class SearchFilterSortFlowExtractor:
    name = "search_filter_sort"
    _QUERY_HINTS = ("?q=", "?search=", "?filter=", "?sort=", "?order=")
    _PATH_HINTS = ("/search", "/filter")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            path = route.path
            if not (
                any(token in path.lower() for token in self._QUERY_HINTS)
                or _route_path_matches(route, self._PATH_HINTS)
            ):
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"search/filter/sort: {route.path}",
                    description="Exercise the search/filter/sort query surface.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Issue a query against {route.path}",
                            target_route_id=route.id,
                            expected_outcome="200 with sorted/filtered results",
                        ),
                    ),
                    priority="P2",
                    risk="medium",
                    confidence=0.7,
                    tags=("search_filter_sort",),
                )
            )
        return tuple(out)


class AdminFlowExtractor:
    name = "admin"
    _PATH_HINTS = ("/admin", "/manage", "/console", "/superuser")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        boundary_role_by_route: dict[str, str | None] = {
            b.route_id: b.required_role for b in graph.auth_boundaries
        }
        for route in graph.routes:
            if not _route_path_matches(route, self._PATH_HINTS):
                continue
            role = boundary_role_by_route.get(route.id)
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"admin: {route.path}",
                    description="Verify admin-only access enforcement.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Anonymous GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="403 or redirect to login",
                        ),
                        FlowStep(
                            description=f"Authenticated non-admin GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="403",
                        ),
                        FlowStep(
                            description=f"Authenticated admin GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="200 with admin UI",
                        ),
                    ),
                    priority="P0",
                    risk="critical",
                    confidence=0.85,
                    required_auth_role=role or "admin",
                    tags=("admin", "authorization"),
                )
            )
        return tuple(out)


class RoleFlowExtractor:
    """Emit one flow per discovered auth_boundary that names a role."""

    name = "role"

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        routes_by_id = _route_index_by_id(graph)
        out: list[Flow] = []
        for boundary in sorted(
            graph.auth_boundaries, key=lambda b: (b.required_role or "", b.route_id)
        ):
            if boundary.required_role is None:
                continue
            route = routes_by_id.get(boundary.route_id)
            if route is None:
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"role:{boundary.required_role} → {route.path}",
                    description=(
                        f"Verify that role={boundary.required_role!r} is required to access "
                        f"{route.path} and lower-privileged roles are denied."
                    ),
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Authenticated lower-privileged GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="403",
                        ),
                        FlowStep(
                            description=f"Authenticated {boundary.required_role} GET {route.path}",
                            target_route_id=route.id,
                            expected_outcome="200 with role-appropriate UI",
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.8,
                    required_auth_role=boundary.required_role,
                    tags=("role", "authorization"),
                )
            )
        return tuple(out)


class FileUploadDownloadFlowExtractor:
    name = "file_upload_download"

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for form in graph.forms:
            has_file = any(field.type == "file" for field in form.fields)
            if not has_file:
                continue
            route = _form_action_route(graph, form)
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name="file upload",
                    description="Upload a small safe sample file and verify the response.",
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description="Pick a small safe sample file (PNG)",
                            expected_outcome="file selector accepts the input",
                        ),
                        FlowStep(
                            description="Submit",
                            target_route_id=route.id if route else None,
                            expected_outcome=(
                                "server returns 200/201 with a downloadable reference; "
                                "no executable types accepted"
                            ),
                        ),
                    ),
                    priority="P1",
                    risk="high",
                    confidence=0.8,
                    tags=("file_upload",),
                )
            )
        # Detect download routes by path keyword.
        for route in graph.routes:
            if "/download" in route.path.lower() or "/export" in route.path.lower():
                out.append(
                    _make_flow(
                        id_generator=id_generator,
                        name=f"file download: {route.path}",
                        description="Download the resource and assert content-type + size.",
                        extractor=self.name,
                        steps=(
                            FlowStep(
                                description=f"GET {route.path}",
                                target_route_id=route.id,
                                expected_outcome=(
                                    "200 with non-empty body and a sensible Content-Type"
                                ),
                            ),
                        ),
                        priority="P2",
                        risk="medium",
                        confidence=0.7,
                        tags=("file_download",),
                    )
                )
        return tuple(out)


class PaymentSandboxFlowExtractor:
    """Detect sandbox payment integrations. Production keys are never used.

    Safety-boundary check: the extractor only proposes flows; it never
    submits real card numbers, and the planner contract requires the
    runner to use the provider's documented sandbox credentials.
    """

    name = "payment_sandbox"
    _PATH_HINTS = ("/checkout", "/payment", "/pay", "/billing", "/subscribe")
    _PROVIDER_TOKENS = ("stripe", "paypal", "square", "braintree", "adyen")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            path = route.path.lower()
            if not _route_path_matches(route, self._PATH_HINTS):
                continue
            provider_seen = next((p for p in self._PROVIDER_TOKENS if p in path), None)
            tags: list[str] = ["payment_sandbox", "sandbox"]
            if provider_seen:
                tags.append(f"provider:{provider_seen}")
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"payment sandbox: {route.path}",
                    description=(
                        "Exercise the payment flow in sandbox mode with the provider's "
                        "documented test cards. Never use production credentials."
                    ),
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"Navigate to {route.path}",
                            target_route_id=route.id,
                            expected_outcome="payment form is visible",
                        ),
                        FlowStep(
                            description="Submit a provider-documented test card",
                            target_route_id=route.id,
                            expected_outcome=(
                                "sandbox returns a success / declined response per the "
                                "provider documentation"
                            ),
                        ),
                    ),
                    priority="P0",
                    risk="critical",
                    confidence=0.75 if provider_seen else 0.65,
                    tags=tags,
                )
            )
        return tuple(out)


class NotificationFlowExtractor:
    name = "notification"
    _PATH_HINTS = ("/verify", "/confirm", "/activate", "/invite")
    _TEMPLATE_TOKENS = ("[token]", "{token}", "[code]", ":token")

    def extract(
        self,
        graph: DiscoveryGraph,
        *,
        id_generator: IdGenerator,
    ) -> tuple[Flow, ...]:
        out: list[Flow] = []
        for route in graph.routes:
            path = route.path.lower()
            looks_like_callback = _route_path_matches(route, self._PATH_HINTS) or any(
                token in path for token in self._TEMPLATE_TOKENS
            )
            if not looks_like_callback:
                continue
            out.append(
                _make_flow(
                    id_generator=id_generator,
                    name=f"notification callback: {route.path}",
                    description=(
                        "Verify a notification/email link callback. The token is opaque; "
                        "fetched fresh from the test environment per run."
                    ),
                    extractor=self.name,
                    steps=(
                        FlowStep(
                            description=f"GET {route.path} with a fresh token",
                            target_route_id=route.id,
                            expected_outcome=("200 with the documented post-action UI / redirect"),
                        ),
                    ),
                    priority="P2",
                    risk="medium",
                    confidence=0.7,
                    tags=("notification",),
                )
            )
        return tuple(out)


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------


def builtin_extractors() -> tuple[FlowExtractor, ...]:
    """Return the canonical, deterministic ordering of built-in extractors."""

    return (
        LoginFlowExtractor(),
        SignupFlowExtractor(),
        LogoutFlowExtractor(),
        PasswordResetFlowExtractor(),
        CrudFlowExtractor(),
        SearchFilterSortFlowExtractor(),
        AdminFlowExtractor(),
        RoleFlowExtractor(),
        FileUploadDownloadFlowExtractor(),
        PaymentSandboxFlowExtractor(),
        NotificationFlowExtractor(),
    )


def run_extractors(
    extractors: Sequence[FlowExtractor],
    graph: DiscoveryGraph,
    *,
    id_generator: IdGenerator,
) -> tuple[Flow, ...]:
    """Run every extractor and return their concatenated flows."""

    out: list[Flow] = []
    for extractor in extractors:
        out.extend(extractor.extract(graph, id_generator=id_generator))
    return tuple(out)


__all__ = [
    "PROPOSAL_THRESHOLD",
    "AdminFlowExtractor",
    "CrudFlowExtractor",
    "FileUploadDownloadFlowExtractor",
    "FlowExtractor",
    "LoginFlowExtractor",
    "LogoutFlowExtractor",
    "NotificationFlowExtractor",
    "PasswordResetFlowExtractor",
    "PaymentSandboxFlowExtractor",
    "RoleFlowExtractor",
    "SearchFilterSortFlowExtractor",
    "SignupFlowExtractor",
    "builtin_extractors",
    "run_extractors",
]
