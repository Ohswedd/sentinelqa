"""GDPR cookie-consent checks.

Three deterministic checks:

1. **Consent banner detection** — heuristics that surface whether a
 consent banner was on the first page load. A missing banner is
 itself a finding (``gdpr:Art.6``) when the operator opts the
 ``consent-banner-missing`` gate in (off by default — many B2B apps
 legitimately do not need a banner).
2. **Cookies set before consent** — any non-essential ``Set-Cookie``
 observed on the first page load (before the user clicked accept)
 is flagged as ``gdpr:Art.6`` / ``cookies-before-consent``.
3. **Asymmetric consent UX** — EDPB Guidelines 03/2022 require that
 *Reject all* is as easy to find as *Accept all*. Banners that need
 the user to drill into a settings panel to reject are flagged as
 ``gdpr:EDPB-03/2022`` / ``asymmetric-consent``.

the engineering guidelines: descriptions begin with *"Automated GDPR
check found …"* — never claim legal GDPR conformance.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from modules.compliance.models import (
    GdprBannerSignal,
    GdprCheckReport,
    GdprCookie,
    GdprIssue,
    GdprPageSignals,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BANNER_TOKEN_RE = re.compile(
    r"\b(cookies?|consent|gdpr|privacy)\b",
    flags=re.IGNORECASE,
)

_ARTICLE_6 = "gdpr:Art.6"
_EDPB_03_2022 = "gdpr:EDPB-03/2022"

_AUTO_PREFIX = "Automated GDPR check found"


# ---------------------------------------------------------------------------
# Banner heuristics (used both as a structured check and as a helper for
# tests that need to drive the detector from raw DOM attributes).
# ---------------------------------------------------------------------------


def looks_like_consent_banner(
    *,
    aria_label: str = "",
    css_id: str = "",
    css_class: str = "",
    role: str = "",
    text_content: str = "",
) -> bool:
    """Return True when the DOM hints look like a consent banner.

    Conservative — only treats ``role="dialog"`` *plus* a cookie token
    or any attribute carrying a cookie / consent / gdpr / privacy token
    as a positive signal.
    """

    if role.lower() == "dialog" and _BANNER_TOKEN_RE.search(text_content or ""):
        return True
    return any(attr and _BANNER_TOKEN_RE.search(attr) for attr in (aria_label, css_id, css_class))


# ---------------------------------------------------------------------------
# Per-page check helpers
# ---------------------------------------------------------------------------


def check_cookies_before_consent(signals: GdprPageSignals) -> tuple[GdprIssue, ...]:
    """Flag every non-essential cookie observed before banner accept.

    The signals' ``cookies_on_first_load`` list is the capture before
    the user interacts with the consent banner. ``essential=True``
    cookies are exempt (session, csrf, locale,...).
    """

    if signals.banner.present:
        # Banner is present — operators may legitimately set strictly
        # necessary cookies regardless. Filter to non-essential ones
        # for the finding either way.
        pass
    issues: list[GdprIssue] = []
    for cookie in signals.cookies_on_first_load:
        if cookie.essential:
            continue
        issues.append(
            GdprIssue(
                category="cookies-before-consent",
                route=signals.route,
                description=(
                    f"{_AUTO_PREFIX}: cookie {cookie.name!r} (domain "
                    f"{cookie.domain or 'unknown'}) was set on the first "
                    f"page-load of {signals.route!r} before the consent "
                    "banner was interacted with."
                ),
                cookie_name=cookie.name,
                compliance_id=_ARTICLE_6,
            )
        )
    return tuple(issues)


def check_consent_banner_missing(
    signals: GdprPageSignals,
) -> tuple[GdprIssue, ...]:
    """Flag pages that load *any* non-essential cookies and have no banner."""

    if signals.banner.present:
        return ()
    non_essential = tuple(c for c in signals.cookies_on_first_load if not c.essential)
    if not non_essential:
        return ()
    return (
        GdprIssue(
            category="consent-banner-missing",
            route=signals.route,
            description=(
                f"{_AUTO_PREFIX}: route {signals.route!r} sets "
                f"{len(non_essential)} non-essential cookie(s) on the first "
                "page-load but no consent banner was detected. A banner "
                "with one-click accept/reject is the EDPB-recommended UX."
            ),
            compliance_id=_ARTICLE_6,
        ),
    )


def check_asymmetric_consent(
    signals: GdprPageSignals,
) -> tuple[GdprIssue, ...]:
    """Flag banners where Reject is harder than Accept (EDPB 03/2022)."""

    banner = signals.banner
    if not banner.present:
        return ()
    if banner.accept_one_click and banner.reject_one_click:
        return ()
    description = (
        f"{_AUTO_PREFIX}: consent banner {banner.selector or signals.route!r} " "is asymmetric — "
    )
    if banner.accept_one_click and not banner.reject_one_click:
        description += (
            "Accept is a single click, but Reject requires the user to "
            "drill into a settings panel. EDPB Guidelines 03/2022 require "
            "Reject to be as easy to find as Accept."
        )
    elif not banner.accept_one_click and banner.reject_one_click:
        description += (
            "Accept requires the user to drill into a settings panel, "
            "which is a different (but still asymmetric) UX bug — both "
            "primary actions should be one click."
        )
    else:
        description += (
            "neither Accept nor Reject is a single-click action — both " "must be one click."
        )
    return (
        GdprIssue(
            category="asymmetric-consent",
            route=signals.route,
            description=description,
            compliance_id=_EDPB_03_2022,
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_gdpr_checks(
    signals: Iterable[GdprPageSignals],
    *,
    flag_missing_banner: bool = False,
) -> GdprCheckReport:
    """Run every GDPR sub-check against the input signals.

    ``flag_missing_banner`` defaults to ``False`` because many B2B apps
    legitimately do not need a banner. The ``gdpr-baseline`` compliance
    pack flips this on; bespoke packs can leave it off.
    """

    issues: list[GdprIssue] = []
    pages_checked = 0
    for page in signals:
        pages_checked += 1
        issues.extend(check_cookies_before_consent(page))
        if flag_missing_banner:
            issues.extend(check_consent_banner_missing(page))
        issues.extend(check_asymmetric_consent(page))
    return GdprCheckReport(
        pages_checked=pages_checked,
        issues=tuple(issues),
    )


__all__ = [
    "check_asymmetric_consent",
    "check_consent_banner_missing",
    "check_cookies_before_consent",
    "looks_like_consent_banner",
    "run_gdpr_checks",
    "GdprBannerSignal",
    "GdprCookie",
    "GdprPageSignals",
]
