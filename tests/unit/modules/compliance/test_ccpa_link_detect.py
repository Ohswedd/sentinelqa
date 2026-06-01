"""CCPA Do Not Sell link detection + opt-out form check."""

from __future__ import annotations

from modules.compliance.ccpa import (
    check_link_presence,
    check_opt_out_form,
    has_do_not_sell_link,
    run_ccpa_checks,
)
from modules.compliance.models import CcpaPageSignal


def _signal(**overrides) -> CcpaPageSignal:
    base = {"route": "/", "link_text": "", "link_href": ""}
    base.update(overrides)
    return CcpaPageSignal(**base)


# ---------------------------------------------------------------------------
# has_do_not_sell_link
# ---------------------------------------------------------------------------


def test_has_link_via_classic_text() -> None:
    assert has_do_not_sell_link(_signal(link_text="Do Not Sell My Personal Information"))


def test_has_link_via_post_2023_text() -> None:
    assert has_do_not_sell_link(_signal(link_text="Your Privacy Choices"))
    assert has_do_not_sell_link(_signal(link_text="Do Not Share My Information"))


def test_has_link_via_href() -> None:
    assert has_do_not_sell_link(_signal(link_href="/privacy-choices"))
    assert has_do_not_sell_link(_signal(link_href="/opt-out"))


def test_no_link_for_generic_privacy_text() -> None:
    assert not has_do_not_sell_link(_signal(link_text="Privacy Policy"))


# ---------------------------------------------------------------------------
# check_link_presence
# ---------------------------------------------------------------------------


def test_link_missing_fires_when_no_text_and_no_href() -> None:
    issues = check_link_presence(_signal(route="/checkout"))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "do-not-sell-link-missing"
    assert issue.compliance_id == "ccpa:do-not-sell-link"
    assert "Automated CCPA check found" in issue.description


def test_link_missing_silent_when_text_present() -> None:
    issues = check_link_presence(
        _signal(link_text="Do Not Sell My Personal Information"),
    )
    assert issues == ()


# ---------------------------------------------------------------------------
# check_opt_out_form
# ---------------------------------------------------------------------------


def test_opt_out_form_silent_when_link_not_followed() -> None:
    issues = check_opt_out_form(
        _signal(
            link_text="Do Not Sell",
            link_href="/dns",
            link_followed=False,
        )
    )
    assert issues == ()


def test_opt_out_form_fires_when_followed_and_form_absent() -> None:
    issues = check_opt_out_form(
        _signal(
            link_text="Do Not Sell",
            link_href="/privacy",
            link_followed=True,
            target_has_opt_out_form=False,
        )
    )
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "do-not-sell-link-opt-out-missing"
    assert issue.compliance_id == "ccpa:do-not-sell-opt-out-form"


def test_opt_out_form_silent_when_form_present() -> None:
    issues = check_opt_out_form(
        _signal(
            link_text="Do Not Sell",
            link_href="/dns",
            link_followed=True,
            target_has_opt_out_form=True,
        )
    )
    assert issues == ()


# ---------------------------------------------------------------------------
# run_ccpa_checks aggregate
# ---------------------------------------------------------------------------


def test_run_aggregates_and_respects_enforce_link_presence() -> None:
    pages = (
        _signal(route="/", link_text="Privacy Policy"),
        _signal(
            route="/account",
            link_text="Do Not Sell",
            link_href="/dns",
            link_followed=True,
            target_has_opt_out_form=False,
        ),
    )
    enforced = run_ccpa_checks(pages, enforce_link_presence=True)
    categories_enforced = {issue.category for issue in enforced.issues}
    assert "do-not-sell-link-missing" in categories_enforced
    assert "do-not-sell-link-opt-out-missing" in categories_enforced

    relaxed = run_ccpa_checks(pages, enforce_link_presence=False)
    categories_relaxed = {issue.category for issue in relaxed.issues}
    assert "do-not-sell-link-missing" not in categories_relaxed
    assert "do-not-sell-link-opt-out-missing" in categories_relaxed
