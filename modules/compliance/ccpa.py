"""CCPA "Do Not Sell or Share" link check.

For every page the crawler discovered the check looks for a
*Do Not Sell or Share My Personal Information* link. Heuristics:

- Link text matches one of: ``do not sell``, ``do not share``,
 ``opt out``, ``opt-out``, ``your privacy choices``.
- ``href`` references a path containing one of ``sell``, ``share``,
 ``opt-out``, ``privacy-choices``.

Pages that lack such a link → :class:`CcpaIssue`
``do-not-sell-link-missing``.

Pages where the link exists, when the crawler followed it once, the
target page must expose an actual opt-out form (input element,
submit button, or a clearly marked toggle). Targets that show a
generic privacy policy without the form → ``do-not-sell-link-opt-out-missing``.

The CCPA detector is deliberately conservative — heuristics, not
NLP. It mirrors the wording rule in the engineering guidelines: descriptions begin
*"Automated CCPA check found …"*; the module never claims legal
CCPA conformance.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from modules.compliance.models import (
    CcpaCheckReport,
    CcpaIssue,
    CcpaPageSignal,
)

# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


_LINK_TEXT_RE = re.compile(
    r"(do\s+not\s+sell|do\s+not\s+share|opt[\s-]*out|your\s+privacy\s+choices)",
    flags=re.IGNORECASE,
)

_LINK_HREF_RE = re.compile(
    r"(sell|share|opt[\s_-]*out|privacy[\s_-]*choices)",
    flags=re.IGNORECASE,
)


_AUTO_PREFIX = "Automated CCPA check found"
_DO_NOT_SELL_ID = "ccpa:do-not-sell-link"
_OPT_OUT_FORM_ID = "ccpa:do-not-sell-opt-out-form"


# ---------------------------------------------------------------------------
# Per-page helpers
# ---------------------------------------------------------------------------


def has_do_not_sell_link(signal: CcpaPageSignal) -> bool:
    """Return True when the page surfaces a Do Not Sell / Share link."""

    text = signal.link_text or ""
    href = signal.link_href or ""
    if text and _LINK_TEXT_RE.search(text):
        return True
    return bool(href and _LINK_HREF_RE.search(href))


def check_link_presence(signal: CcpaPageSignal) -> tuple[CcpaIssue, ...]:
    """Flag pages without a Do Not Sell / Share link."""

    if has_do_not_sell_link(signal):
        return ()
    return (
        CcpaIssue(
            category="do-not-sell-link-missing",
            route=signal.route,
            description=(
                f"{_AUTO_PREFIX}: route {signal.route!r} does not surface a "
                '"Do Not Sell or Share My Personal Information" link. '
                "CCPA requires a clear, conspicuous opt-out link for "
                "California residents."
            ),
            compliance_id=_DO_NOT_SELL_ID,
        ),
    )


def check_opt_out_form(signal: CcpaPageSignal) -> tuple[CcpaIssue, ...]:
    """Flag pages where the link target lacks an actual opt-out form."""

    if not has_do_not_sell_link(signal):
        return ()
    if not signal.link_followed:
        return ()
    if signal.target_has_opt_out_form:
        return ()
    return (
        CcpaIssue(
            category="do-not-sell-link-opt-out-missing",
            route=signal.route,
            description=(
                f"{_AUTO_PREFIX}: the Do Not Sell / Share link from "
                f"{signal.route!r} targets {signal.link_href!r}, but the "
                "target page does not appear to expose an actual opt-out "
                "form — only a privacy-policy document. The link must "
                "lead to a working opt-out mechanism."
            ),
            compliance_id=_OPT_OUT_FORM_ID,
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_ccpa_checks(
    signals: Iterable[CcpaPageSignal],
    *,
    enforce_link_presence: bool = True,
) -> CcpaCheckReport:
    """Run every CCPA sub-check against the input signals.

    ``enforce_link_presence`` defaults to True (the ``ccpa-baseline``
    pack uses it). Operators serving non-US-shaped audiences can flip
    the gate off and still benefit from the link-target verification.
    """

    issues: list[CcpaIssue] = []
    pages_checked = 0
    for page in signals:
        pages_checked += 1
        if enforce_link_presence:
            issues.extend(check_link_presence(page))
        issues.extend(check_opt_out_form(page))
    return CcpaCheckReport(
        pages_checked=pages_checked,
        issues=tuple(issues),
    )


__all__ = [
    "check_link_presence",
    "check_opt_out_form",
    "has_do_not_sell_link",
    "run_ccpa_checks",
    "CcpaPageSignal",
]
