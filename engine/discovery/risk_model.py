"""Deterministic risk rules.

A small, audited set of explainable rules. Each rule is a pure function
``(RuleContext) -> RuleVerdict | None`` so the unit tests can pin every
input → output mapping. The aggregate score is clipped to ``[0, 1]``.

Adding a rule requires:

1. A new entry in :data:`RISK_RULES` (kept sorted by rule name).
2. A docstring naming the rule slug — the rule name is exactly what
 appears in ``RouteRisk.justifications``, so users and ADRs reference
 the same string.
3. A test in ``tests/unit/discovery/test_risk_model.py`` for both the
 positive and negative case.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from engine.discovery.api_detector import ApiSuspicion
from engine.discovery.dom_map import DomObservation
from engine.discovery.forms import FormObservation
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.element import Element
from engine.domain.route import Route


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule needs to make a verdict on a single route."""

    route: Route
    route_url: str
    elements_on_route: tuple[Element, ...]
    forms_on_route: tuple[str, ...]
    dom_observations_on_route: tuple[DomObservation, ...]
    form_observations_on_route: tuple[FormObservation, ...]
    api_suspicions_on_route: tuple[ApiSuspicion, ...]
    crawl_status_code: int
    crawl_failed: bool
    api_endpoints_on_route: tuple[ApiEndpoint, ...]


@dataclass(frozen=True)
class RuleVerdict:
    """A single rule's contribution to the route's risk score."""

    name: str
    weight: float
    detail: str


RiskRule = Callable[[RuleContext], RuleVerdict | None]


def _path_contains(route_url: str, tokens: Sequence[str]) -> bool:
    lower = urlparse(route_url).path.lower()
    return any(tok in lower for tok in tokens)


def rule_login_auth_critical(ctx: RuleContext) -> RuleVerdict | None:
    """High base risk on login / auth / signin routes."""

    if _path_contains(ctx.route_url, ("/login", "/signin", "/sign-in", "/auth")):
        return RuleVerdict("login_auth_critical", 0.6, "auth-related route")
    return None


def rule_admin_route(ctx: RuleContext) -> RuleVerdict | None:
    """Admin paths are high risk; mistakes here turn into authz bugs."""

    if _path_contains(ctx.route_url, ("/admin", "/internal", "/staff")):
        return RuleVerdict("admin_route", 0.5, "admin-only route")
    return None


def rule_payment_flow(ctx: RuleContext) -> RuleVerdict | None:
    """Payment / billing / checkout — financial blast radius."""

    if _path_contains(ctx.route_url, ("/checkout", "/payment", "/billing", "/cart")):
        return RuleVerdict("payment_flow", 0.55, "payment-related route")
    return None


def rule_5xx_during_discovery(ctx: RuleContext) -> RuleVerdict | None:
    """5xx during discovery is the strongest signal — the route is broken."""

    if 500 <= ctx.crawl_status_code < 600:
        return RuleVerdict(
            "5xx_during_discovery",
            0.95,
            f"crawl saw status {ctx.crawl_status_code}",
        )
    return None


def rule_unreachable_route(ctx: RuleContext) -> RuleVerdict | None:
    if 400 <= ctx.crawl_status_code < 500 and ctx.crawl_status_code not in (401, 403):
        return RuleVerdict(
            "unreachable_route",
            0.4,
            f"crawl saw status {ctx.crawl_status_code}",
        )
    return None


def rule_form_without_submit(ctx: RuleContext) -> RuleVerdict | None:
    """Form on the page with no action / onsubmit / API call = fake completeness."""

    if any(o.kind == "form_missing_submit_handler" for o in ctx.form_observations_on_route):
        return RuleVerdict(
            "form_without_submit",
            0.5,
            "form has no action / onsubmit / API hookup",
        )
    return None


def rule_form_without_validation(ctx: RuleContext) -> RuleVerdict | None:
    if any(o.kind == "form_missing_client_validation" for o in ctx.form_observations_on_route):
        return RuleVerdict(
            "form_without_validation",
            0.2,
            "form has no client-side validation hints",
        )
    return None


def rule_missing_accessible_labels(ctx: RuleContext) -> RuleVerdict | None:
    if any(o.kind == "input_missing_label" for o in ctx.dom_observations_on_route):
        return RuleVerdict(
            "missing_accessible_labels",
            0.15,
            "inputs without associated labels",
        )
    if any(o.kind == "missing_accessible_name" for o in ctx.dom_observations_on_route):
        return RuleVerdict(
            "missing_accessible_labels",
            0.1,
            "interactive elements without accessible names",
        )
    return None


def rule_api_referenced_only(ctx: RuleContext) -> RuleVerdict | None:
    if any(s.kind == "referenced_only" for s in ctx.api_suspicions_on_route):
        return RuleVerdict(
            "api_referenced_only",
            0.45,
            "endpoints referenced in JS but never reached",
        )
    return None


def rule_crawl_failed(ctx: RuleContext) -> RuleVerdict | None:
    if ctx.crawl_failed:
        return RuleVerdict(
            "crawl_failed",
            0.8,
            "crawler could not reach the route (network/DNS error)",
        )
    return None


# Order matters only for tie-breakers; rules themselves are additive.
RISK_RULES: tuple[RiskRule, ...] = (
    rule_5xx_during_discovery,
    rule_admin_route,
    rule_api_referenced_only,
    rule_crawl_failed,
    rule_form_without_submit,
    rule_form_without_validation,
    rule_login_auth_critical,
    rule_missing_accessible_labels,
    rule_payment_flow,
    rule_unreachable_route,
)


def score_route(ctx: RuleContext) -> tuple[float, tuple[str, ...]]:
    """Apply every rule to ``ctx`` and return ``(score, justifications)``."""

    total = 0.0
    justifications: list[str] = []
    for rule in RISK_RULES:
        verdict = rule(ctx)
        if verdict is None:
            continue
        total += verdict.weight
        justifications.append(f"{verdict.name}: {verdict.detail}")
    if total > 1.0:
        total = 1.0
    if total < 0.0:
        total = 0.0
    return total, tuple(justifications)


__all__ = [
    "RISK_RULES",
    "RiskRule",
    "RuleContext",
    "RuleVerdict",
    "rule_5xx_during_discovery",
    "rule_admin_route",
    "rule_api_referenced_only",
    "rule_crawl_failed",
    "rule_form_without_submit",
    "rule_form_without_validation",
    "rule_login_auth_critical",
    "rule_missing_accessible_labels",
    "rule_payment_flow",
    "rule_unreachable_route",
    "score_route",
]
