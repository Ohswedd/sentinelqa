# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Cookie consent → cookie-behaviour parity (v1.3.0).

The shipping GDPR pack detects whether a consent banner is rendered
before any non-essential cookies are set. This module adds the
complementary check: *withdrawing* consent must actually clear those
cookies.

The real-world flow the check models:

1. Load the page → record the cookie jar (``initial``).
2. Click the "Reject all" / "Withdraw consent" affordance → record
   the cookie jar (``post_reject``).
3. Compute the symmetric difference between the two jars.

Cookies whose name matches the well-known *strictly necessary*
allowlist (session, CSRF, locale, theme) are excluded from the
diff — these are exempt from the consent regime per the EDPB
guidance referenced from
``modules/compliance/gdpr.py``.

Any non-essential cookie that *remains* after the reject click is
a finding. Severity ladders by the kind of cookie that survived
(tracking > marketing > analytics > unknown).

The helpers in this module are pure — they take ``CookieRecord``
sequences as input and return findings. The Playwright bridge
fetches the jars; this module classifies them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class CookieRecord:
    """A single cookie as observed by a browser."""

    name: str
    domain: str
    value_preview: str = ""  # already redacted before reaching this module
    secure: bool = False
    http_only: bool = False
    same_site: str | None = None


@dataclass(frozen=True, slots=True)
class CookieClassification:
    """The category we map a cookie name into."""

    kind: Literal["strictly_necessary", "analytics", "marketing", "tracking", "unknown"]
    rationale: str


@dataclass(frozen=True, slots=True)
class ParityFinding:
    """A non-essential cookie that survived the reject-all click."""

    cookie: CookieRecord
    classification: CookieClassification
    severity: Severity
    title: str
    description: str
    compliance_id: str = "gdpr:Art.6"


# --------------------------------------------------------------------------- #
# Cookie classification heuristics
# --------------------------------------------------------------------------- #


_STRICTLY_NECESSARY_NAMES: Final[frozenset[str]] = frozenset(
    {
        "sessionid",
        "session_id",
        "session",
        "csrftoken",
        "csrf_token",
        "xsrf_token",
        "next-auth.csrf-token",
        "next-auth.session-token",
        "auth_token",
        "language",
        "locale",
        "lang",
        "theme",
        "color-mode",
        "cookieconsent_status",
        "cookieconsent",
        "cookie_consent",
        "consent",
        "intercom-id",
    }
)


# Cookie-name patterns from common trackers (Google Analytics,
# Facebook Pixel, etc.). Conservative — strings that almost only
# appear in those contexts.
_PATTERNS: Final[dict[str, tuple[re.Pattern[str], ...]]] = {
    "analytics": (
        re.compile(r"^_ga(_.*)?$"),  # Google Analytics
        re.compile(r"^_gid$"),
        re.compile(r"^_gat(_.*)?$"),
        re.compile(r"^ai_(session|user)$"),  # Azure App Insights
        re.compile(r"^_hjSession.*$"),  # Hotjar
        re.compile(r"^amplitude_id_.*$"),
        re.compile(r"^mp_.*_mixpanel$"),
    ),
    "marketing": (
        re.compile(r"^_fbp$"),
        re.compile(r"^_fbc$"),
        re.compile(r"^fr$", re.IGNORECASE),  # Facebook
        re.compile(r"^_gcl_.*$"),  # Google Ads click
        re.compile(r"^_uetsid$|^_uetvid$"),  # Microsoft UET
        re.compile(r"^IDE$"),  # DoubleClick
        re.compile(r"^MUID$"),  # Microsoft
    ),
    "tracking": (
        re.compile(r"^drift_session_.*$"),
        re.compile(r"^MUIDB?$"),
        re.compile(r"^datr$", re.IGNORECASE),  # Facebook persistence
        re.compile(r"^optimizelyEndUserId$"),
        re.compile(r"^segment_.*$"),
    ),
}


def classify_cookie(record: CookieRecord) -> CookieClassification:
    """Map a cookie record to its consent-regime category."""

    name = record.name.lower()
    if name in _STRICTLY_NECESSARY_NAMES:
        return CookieClassification(
            kind="strictly_necessary",
            rationale="Name is on the documented strictly-necessary allowlist.",
        )
    for kind, patterns in _PATTERNS.items():
        for pattern in patterns:
            if pattern.search(record.name):
                return CookieClassification(
                    kind=kind,  # type: ignore[arg-type]
                    rationale=f"Matched {kind} pattern {pattern.pattern!r}",
                )
    return CookieClassification(
        kind="unknown",
        rationale="Cookie name did not match any classification heuristic.",
    )


# --------------------------------------------------------------------------- #
# Parity diff
# --------------------------------------------------------------------------- #


def survivors_after_reject(
    initial_jar: list[CookieRecord],
    post_reject_jar: list[CookieRecord],
) -> tuple[CookieRecord, ...]:
    """Return the cookies that are still present after the reject click.

    The "still present" condition is: same ``(name, domain)`` key
    appearing in both jars.
    """

    keys_post = {(c.name, c.domain) for c in post_reject_jar}
    return tuple(
        sorted(
            (c for c in initial_jar if (c.name, c.domain) in keys_post),
            key=lambda c: (c.domain, c.name),
        )
    )


_SEVERITY_BY_KIND: Final[dict[str, Severity]] = {
    "tracking": "high",
    "marketing": "high",
    "analytics": "medium",
    "unknown": "low",
    "strictly_necessary": "info",
}


def find_parity_violations(
    initial_jar: list[CookieRecord],
    post_reject_jar: list[CookieRecord],
) -> tuple[ParityFinding, ...]:
    """Return one finding per non-essential cookie that survived reject."""

    survivors = survivors_after_reject(initial_jar, post_reject_jar)
    out: list[ParityFinding] = []
    for cookie in survivors:
        classification = classify_cookie(cookie)
        if classification.kind == "strictly_necessary":
            continue
        severity = _SEVERITY_BY_KIND[classification.kind]
        title = (
            f"{classification.kind.title()} cookie {cookie.name!r} " "survived the reject-all click"
        )
        description = (
            f"Cookie {cookie.name!r} on {cookie.domain!r} was still "
            "present after the consent withdrawal flow completed. "
            f"Classification: {classification.kind}. "
            f"Rationale: {classification.rationale}"
        )
        out.append(
            ParityFinding(
                cookie=cookie,
                classification=classification,
                severity=severity,
                title=title,
                description=description,
            )
        )
    return tuple(out)


__all__ = [
    "CookieClassification",
    "CookieRecord",
    "ParityFinding",
    "classify_cookie",
    "find_parity_violations",
    "survivors_after_reject",
]
