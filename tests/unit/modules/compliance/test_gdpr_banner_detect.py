"""Phase 34.02 — GDPR consent-banner detection + cookies-before-consent."""

from __future__ import annotations

from modules.compliance.gdpr import (
    check_asymmetric_consent,
    check_consent_banner_missing,
    check_cookies_before_consent,
    looks_like_consent_banner,
    run_gdpr_checks,
)
from modules.compliance.models import (
    GdprBannerSignal,
    GdprCookie,
    GdprPageSignals,
)

# ---------------------------------------------------------------------------
# looks_like_consent_banner heuristics
# ---------------------------------------------------------------------------


def test_banner_detected_via_aria_label() -> None:
    assert looks_like_consent_banner(aria_label="Cookie consent dialog")


def test_banner_detected_via_id_class() -> None:
    assert looks_like_consent_banner(css_id="gdpr-banner")
    assert looks_like_consent_banner(css_class="cookie-consent-bar")


def test_banner_detected_via_role_and_text() -> None:
    assert looks_like_consent_banner(
        role="dialog",
        text_content="We use cookies to improve your experience.",
    )


def test_unrelated_dialog_is_not_a_banner() -> None:
    assert not looks_like_consent_banner(
        role="dialog",
        text_content="Subscribe to our newsletter",
    )


def test_empty_inputs_negative() -> None:
    assert not looks_like_consent_banner()


# ---------------------------------------------------------------------------
# Cookies before consent
# ---------------------------------------------------------------------------


def test_cookies_before_consent_flags_non_essential_cookies() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(present=True),
        cookies_on_first_load=(
            GdprCookie(name="_ga", domain="example.test"),
            GdprCookie(name="sessionid", domain="example.test", essential=True),
        ),
    )
    issues = check_cookies_before_consent(signals)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "cookies-before-consent"
    assert issue.cookie_name == "_ga"
    assert issue.compliance_id == "gdpr:Art.6"
    assert "Automated GDPR check found" in issue.description


def test_cookies_before_consent_silent_when_only_essential() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(present=True),
        cookies_on_first_load=(
            GdprCookie(name="sessionid", essential=True),
            GdprCookie(name="csrf", essential=True),
        ),
    )
    assert check_cookies_before_consent(signals) == ()


def test_consent_banner_missing_silent_when_no_cookies() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(present=False),
        cookies_on_first_load=(),
    )
    assert check_consent_banner_missing(signals) == ()


def test_consent_banner_missing_fires_when_cookies_present() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(present=False),
        cookies_on_first_load=(GdprCookie(name="_ga"),),
    )
    issues = check_consent_banner_missing(signals)
    assert len(issues) == 1
    assert issues[0].category == "consent-banner-missing"
    assert issues[0].compliance_id == "gdpr:Art.6"


# ---------------------------------------------------------------------------
# Asymmetric consent
# ---------------------------------------------------------------------------


def test_asymmetric_consent_fires_when_only_accept_one_click() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(
            present=True,
            accept_one_click=True,
            reject_one_click=False,
            selector="#consent",
        ),
    )
    issues = check_asymmetric_consent(signals)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "asymmetric-consent"
    assert issue.compliance_id == "gdpr:EDPB-03/2022"
    assert "Reject" in issue.description


def test_asymmetric_consent_silent_when_both_one_click() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(present=True),
    )
    assert check_asymmetric_consent(signals) == ()


def test_asymmetric_consent_silent_when_banner_absent() -> None:
    signals = GdprPageSignals(
        route="/",
        banner=GdprBannerSignal(
            present=False,
            accept_one_click=False,
            reject_one_click=False,
        ),
    )
    assert check_asymmetric_consent(signals) == ()


# ---------------------------------------------------------------------------
# run_gdpr_checks aggregate
# ---------------------------------------------------------------------------


def test_run_gdpr_checks_aggregates_and_respects_flag_missing_banner() -> None:
    pages = (
        GdprPageSignals(
            route="/",
            banner=GdprBannerSignal(present=False),
            cookies_on_first_load=(GdprCookie(name="_ga"),),
        ),
    )
    no_flag = run_gdpr_checks(pages, flag_missing_banner=False)
    # The cookies-before-consent finding always fires; the
    # consent-banner-missing only when explicitly enabled.
    assert no_flag.pages_checked == 1
    categories_no_flag = {issue.category for issue in no_flag.issues}
    assert "cookies-before-consent" in categories_no_flag
    assert "consent-banner-missing" not in categories_no_flag

    with_flag = run_gdpr_checks(pages, flag_missing_banner=True)
    categories_with_flag = {issue.category for issue in with_flag.issues}
    assert "consent-banner-missing" in categories_with_flag
