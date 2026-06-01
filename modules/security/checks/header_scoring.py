# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Strictness scoring for response-header hygiene (v1.3.0).

The original headers check (`modules.security.checks.headers`) is
binary — a header is present or absent. That doesn't capture *how
strict* a Content-Security-Policy is, or *how much of* a page's
third-party JavaScript is covered by Subresource Integrity, or
*how close* an HSTS header is to being preload-eligible.

This module fills the gap. Each scorer is a pure function with a
clear output schema; the security module composes them into
:class:`SecurityIssue` records for the headers check artifact.

Three scorers:

* :func:`score_csp` — Content-Security-Policy. Penalties: missing,
  ``'unsafe-inline'`` / ``'unsafe-eval'``, wildcard sources,
  ``http:`` / ``ws:`` in directives, missing default-src, missing
  frame-ancestors, no report-uri.
* :func:`score_sri` — Subresource Integrity. Pure HTML scan: every
  ``<script src=>`` and ``<link rel="stylesheet" href=>`` that
  points off-host is expected to carry an ``integrity`` attribute.
  Score = fraction of third-party resources covered.
* :func:`score_hsts` — HSTS preload eligibility per
  https://hstspreload.org/ rules: max-age >= 31536000,
  ``includeSubDomains``, ``preload`` directive, served over HTTPS.

Outputs are :class:`ScoringResult` records with ``score`` in [0, 100],
``severity`` in the standard ladder, and a ``reasons`` list explaining
each penalty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal
from urllib.parse import urlparse

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """One scorer's output."""

    name: str
    score: int  # 0-100
    severity: Severity
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return self.score >= 90 and self.severity in {"info", "low"}


# --------------------------------------------------------------------------- #
# CSP scoring
# --------------------------------------------------------------------------- #

# Each penalty maps to a "points off" value; the score starts at 100.
_CSP_PENALTIES: Final[dict[str, int]] = {
    "missing": 100,
    "unsafe-inline": 40,
    "unsafe-eval": 30,
    "wildcard-source": 30,
    "http-scheme": 20,
    "ws-scheme": 10,
    "no-default-src": 15,
    "no-frame-ancestors": 10,
    "no-object-src": 5,
    "no-report-uri": 5,
}


def score_csp(csp: str | None) -> ScoringResult:
    """Score a Content-Security-Policy header value.

    Returns a fresh :class:`ScoringResult` regardless of input — a
    ``None`` CSP produces ``score=0`` and the ``"missing"`` reason.
    """

    if csp is None or not csp.strip():
        return ScoringResult(
            name="csp",
            score=0,
            severity="high",
            reasons=("CSP header missing",),
        )

    lowered = csp.lower()
    reasons: list[str] = []
    score = 100

    if "'unsafe-inline'" in lowered:
        reasons.append("'unsafe-inline' present — defeats most XSS protection")
        score -= _CSP_PENALTIES["unsafe-inline"]
    if "'unsafe-eval'" in lowered:
        reasons.append("'unsafe-eval' present — defeats most XSS protection")
        score -= _CSP_PENALTIES["unsafe-eval"]
    if " * " in f" {lowered} " or "*;" in lowered or lowered.endswith("*"):
        reasons.append("Wildcard '*' source — restricts almost nothing")
        score -= _CSP_PENALTIES["wildcard-source"]
    if "http:" in lowered:
        reasons.append("http: scheme allowed — mixed-content vector")
        score -= _CSP_PENALTIES["http-scheme"]
    if "ws:" in lowered:
        reasons.append("ws: scheme allowed — should be wss:")
        score -= _CSP_PENALTIES["ws-scheme"]
    if "default-src" not in lowered:
        reasons.append("default-src missing — undeclared directives fall back to *")
        score -= _CSP_PENALTIES["no-default-src"]
    if "frame-ancestors" not in lowered:
        reasons.append("frame-ancestors missing — clickjacking protection incomplete")
        score -= _CSP_PENALTIES["no-frame-ancestors"]
    if "object-src" not in lowered:
        reasons.append("object-src missing — Flash/legacy plugin gap")
        score -= _CSP_PENALTIES["no-object-src"]
    if "report-uri" not in lowered and "report-to" not in lowered:
        reasons.append("No report-uri/report-to — violations are invisible")
        score -= _CSP_PENALTIES["no-report-uri"]

    score = max(0, min(score, 100))
    severity = _severity_from_score(score, high_floor=60, medium_floor=80)
    return ScoringResult(name="csp", score=score, severity=severity, reasons=tuple(reasons))


# --------------------------------------------------------------------------- #
# SRI scoring
# --------------------------------------------------------------------------- #

# Pull every <script src=...> and <link rel="stylesheet" href=...> with
# their associated integrity attribute (or lack of one).
_SCRIPT_RE = re.compile(
    r"<script\b([^>]*)>",
    re.IGNORECASE,
)
_LINK_RE = re.compile(
    r"<link\b([^>]*?)>",
    re.IGNORECASE,
)
_SRC_RE = re.compile(r'\bsrc\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_HREF_RE = re.compile(r'\bhref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_REL_RE = re.compile(r'\brel\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_INTEGRITY_RE = re.compile(
    r'\bintegrity\s*=\s*["\']\s*(sha\d+-[A-Za-z0-9+/=]+)\s*["\']',
    re.IGNORECASE,
)


def _is_off_host(resource_url: str, page_origin: str) -> bool:
    """Return True if ``resource_url`` points at a different origin."""

    if not resource_url:
        return False
    if resource_url.startswith(("data:", "javascript:", "blob:", "#")):
        return False
    if resource_url.startswith("//"):
        # Schemeless absolute — host is the second component.
        parsed = urlparse(f"https:{resource_url}")
        return _origin(parsed) != page_origin
    parsed = urlparse(resource_url)
    if parsed.scheme in ("", "/"):
        return False
    if not parsed.netloc:
        return False
    return _origin(parsed) != page_origin


def _origin(parsed: object) -> str:
    netloc = getattr(parsed, "netloc", "")
    scheme = getattr(parsed, "scheme", "")
    return f"{scheme}://{netloc}".lower() if netloc else ""


def score_sri(html: str, *, page_origin: str) -> ScoringResult:
    """Score Subresource Integrity coverage of off-host scripts + stylesheets.

    Pure HTML scan — does not fetch the resources. The score is the
    percentage of off-host script/link tags that carry a valid
    ``integrity`` attribute. Same-origin resources are excluded from
    the denominator (SRI is not required for them).
    """

    if not html.strip():
        return ScoringResult(
            name="sri",
            score=100,
            severity="info",
            reasons=("No HTML body to scan",),
        )

    off_host_total = 0
    covered = 0
    uncovered_sample: list[str] = []

    for match in _SCRIPT_RE.finditer(html):
        attrs = match.group(1)
        src_match = _SRC_RE.search(attrs)
        if src_match is None:
            continue
        src = src_match.group(1)
        if not _is_off_host(src, page_origin):
            continue
        off_host_total += 1
        if _INTEGRITY_RE.search(attrs) is not None:
            covered += 1
        elif len(uncovered_sample) < 5:
            uncovered_sample.append(src)

    for match in _LINK_RE.finditer(html):
        attrs = match.group(1)
        rel_match = _REL_RE.search(attrs)
        if rel_match is None or "stylesheet" not in rel_match.group(1).lower():
            continue
        href_match = _HREF_RE.search(attrs)
        if href_match is None:
            continue
        href = href_match.group(1)
        if not _is_off_host(href, page_origin):
            continue
        off_host_total += 1
        if _INTEGRITY_RE.search(attrs) is not None:
            covered += 1
        elif len(uncovered_sample) < 5:
            uncovered_sample.append(href)

    if off_host_total == 0:
        return ScoringResult(
            name="sri",
            score=100,
            severity="info",
            reasons=("No off-host scripts/stylesheets detected",),
        )

    coverage = covered / off_host_total
    score = int(round(coverage * 100))
    reasons: list[str] = [
        f"{covered}/{off_host_total} off-host resource(s) carry an integrity attribute",
    ]
    if uncovered_sample:
        reasons.append("Uncovered samples: " + ", ".join(uncovered_sample))

    severity = _severity_from_score(score, high_floor=50, medium_floor=80)
    return ScoringResult(name="sri", score=score, severity=severity, reasons=tuple(reasons))


# --------------------------------------------------------------------------- #
# HSTS preload scoring
# --------------------------------------------------------------------------- #

_MAX_AGE_RE = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)
_MIN_MAX_AGE_FOR_PRELOAD = 31_536_000  # one year, per hstspreload.org


def score_hsts(
    hsts: str | None,
    *,
    is_https: bool,
) -> ScoringResult:
    """Score HSTS preload eligibility.

    Per https://hstspreload.org/, a domain qualifies for the Chrome
    preload list when it serves HSTS with all of:
      * ``max-age >= 31536000`` (one year),
      * ``includeSubDomains``,
      * ``preload``,
      * over HTTPS with a valid certificate (caller indicates via
        ``is_https``).
    """

    if not is_https:
        return ScoringResult(
            name="hsts",
            score=0,
            severity="medium",
            reasons=("Target is not HTTPS — HSTS is meaningless on cleartext.",),
        )
    if hsts is None or not hsts.strip():
        return ScoringResult(
            name="hsts",
            score=0,
            severity="high",
            reasons=("HSTS header missing",),
        )

    lowered = hsts.lower()
    reasons: list[str] = []
    score = 100

    max_age_match = _MAX_AGE_RE.search(lowered)
    if max_age_match is None:
        reasons.append("max-age directive missing")
        score -= 40
        max_age = 0
    else:
        max_age = int(max_age_match.group(1))
        if max_age < _MIN_MAX_AGE_FOR_PRELOAD:
            reasons.append(
                f"max-age={max_age} is below preload floor " f"({_MIN_MAX_AGE_FOR_PRELOAD})"
            )
            score -= 30

    if "includesubdomains" not in lowered:
        reasons.append("includeSubDomains directive missing")
        score -= 20
    if "preload" not in lowered:
        reasons.append("preload directive missing")
        score -= 20

    score = max(0, min(score, 100))
    severity = _severity_from_score(score, high_floor=40, medium_floor=80)
    if not reasons:
        reasons.append("Eligible for the HSTS preload list")
    return ScoringResult(name="hsts", score=score, severity=severity, reasons=tuple(reasons))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _severity_from_score(score: int, *, high_floor: int, medium_floor: int) -> Severity:
    """Map a 0-100 score to the standard severity ladder."""

    if score < high_floor:
        return "high"
    if score < medium_floor:
        return "medium"
    if score < 95:
        return "low"
    return "info"


__all__ = [
    "ScoringResult",
    "score_csp",
    "score_hsts",
    "score_sri",
]
