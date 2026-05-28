"""Unit tests covering every rule in :mod:`engine.discovery.risk_model`."""

from __future__ import annotations

import pytest
from engine.discovery.api_detector import ApiSuspicion
from engine.discovery.dom_map import DomObservation
from engine.discovery.forms import FormObservation
from engine.discovery.risk_model import (
    RISK_RULES,
    RuleContext,
    score_route,
)
from engine.domain.route import Route


def _route(path: str = "/", auth_required: bool = False) -> Route:
    return Route(id="RT-AAAAAAAAAAAA", path=path, auth_required=auth_required)


def _ctx(
    *,
    route_url: str = "https://example.com/",
    crawl_status_code: int = 200,
    crawl_failed: bool = False,
    dom_observations: tuple[DomObservation, ...] = (),
    form_observations: tuple[FormObservation, ...] = (),
    api_suspicions: tuple[ApiSuspicion, ...] = (),
) -> RuleContext:
    return RuleContext(
        route=_route(),
        route_url=route_url,
        elements_on_route=(),
        forms_on_route=(),
        dom_observations_on_route=dom_observations,
        form_observations_on_route=form_observations,
        api_suspicions_on_route=api_suspicions,
        crawl_status_code=crawl_status_code,
        crawl_failed=crawl_failed,
        api_endpoints_on_route=(),
    )


def test_zero_signal_yields_zero_score() -> None:
    score, justifications = score_route(_ctx())
    assert score == 0.0
    assert justifications == ()


def test_login_path_scores_above_zero() -> None:
    score, justifications = score_route(_ctx(route_url="https://example.com/login"))
    assert score >= 0.6
    assert any("login_auth_critical" in j for j in justifications)


@pytest.mark.parametrize(
    ("path", "expected_rule"),
    [
        ("/admin", "admin_route"),
        ("/internal/dashboard", "admin_route"),
        ("/checkout", "payment_flow"),
        ("/billing/invoice", "payment_flow"),
    ],
)
def test_path_keyword_rules(path: str, expected_rule: str) -> None:
    score, justifications = score_route(_ctx(route_url=f"https://example.com{path}"))
    assert score > 0
    assert any(expected_rule in j for j in justifications)


def test_5xx_dominates() -> None:
    score, justifications = score_route(_ctx(crawl_status_code=503))
    assert score == pytest.approx(0.95)
    assert any("5xx_during_discovery" in j for j in justifications)


def test_5xx_and_login_clip_at_1() -> None:
    score, _ = score_route(_ctx(route_url="https://example.com/login", crawl_status_code=500))
    assert score == 1.0


def test_unreachable_4xx_signals_risk() -> None:
    score, justifications = score_route(_ctx(crawl_status_code=404))
    assert score == pytest.approx(0.4)
    assert any("unreachable_route" in j for j in justifications)


def test_401_403_not_flagged_as_unreachable() -> None:
    # Auth-protected pages are NOT broken — they should not raise risk.
    score_401, _ = score_route(_ctx(crawl_status_code=401))
    score_403, _ = score_route(_ctx(crawl_status_code=403))
    assert score_401 == 0.0
    assert score_403 == 0.0


def test_form_without_submit_flagged() -> None:
    obs = FormObservation(
        form_id="FRM-AAAAAAAAAAAA",
        route_url="https://example.com/",
        kind="form_missing_submit_handler",
        detail="",
    )
    score, justifications = score_route(_ctx(form_observations=(obs,)))
    assert score >= 0.5
    assert any("form_without_submit" in j for j in justifications)


def test_form_without_validation_flagged() -> None:
    obs = FormObservation(
        form_id="FRM-AAAAAAAAAAAA",
        route_url="https://example.com/",
        kind="form_missing_client_validation",
        detail="",
    )
    score, justifications = score_route(_ctx(form_observations=(obs,)))
    assert score >= 0.2
    assert any("form_without_validation" in j for j in justifications)


def test_missing_input_labels_flagged() -> None:
    obs = DomObservation(
        route_url="https://example.com/",
        element_id="EL-AAAAAAAAAAAA",
        kind="input_missing_label",
        detail="",
    )
    score, _ = score_route(_ctx(dom_observations=(obs,)))
    assert score == pytest.approx(0.15)


def test_missing_accessible_name_flagged() -> None:
    obs = DomObservation(
        route_url="https://example.com/",
        element_id="EL-AAAAAAAAAAAA",
        kind="missing_accessible_name",
        detail="",
    )
    score, _ = score_route(_ctx(dom_observations=(obs,)))
    assert score == pytest.approx(0.1)


def test_api_referenced_only_flagged() -> None:
    sus = ApiSuspicion(
        endpoint_path="/api/users",
        kind="referenced_only",
        detail="never reached",
    )
    score, justifications = score_route(_ctx(api_suspicions=(sus,)))
    assert score == pytest.approx(0.45)
    assert any("api_referenced_only" in j for j in justifications)


def test_crawl_failed_flagged() -> None:
    score, _ = score_route(_ctx(crawl_failed=True))
    assert score == pytest.approx(0.8)


def test_rule_count_matches_export() -> None:
    # Sanity that every rule documented in the module is exported.
    assert len(RISK_RULES) == 10
