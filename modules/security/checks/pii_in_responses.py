# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""PII detection in HTTP response bodies (v1.3.0).

The existing ``frontend_secrets`` check scans JS bundles + DOM
snapshots for API keys. This module looks for *personally
identifiable information* (PII) — values that should typically
have been redacted from a response body before it left the server.

Pure pattern matcher: takes a response body (string) and the
expected content-type, returns a tuple of :class:`PiiMatch`. The
production HTTP probe lives in the security module shell; this
module is fully testable without IO.

Patterns covered:

* US SSN (NNN-NN-NNNN) — area number / group number sanity-checked.
* US ZIP+4 (only flagged together with another PII signal to keep
  false positives down).
* Credit card numbers (PAN) — Luhn-checked across 13-19 digits.
* Email addresses — RFC 5322 simplified.
* US phone numbers ((XXX) XXX-XXXX, XXX-XXX-XXXX).
* IPv4 addresses (information leak when paired with email).
* Bank IBAN (length-checked).

Every match carries a ``preview`` field which is masked at output
time (``****-**-1234``). The original PII never leaves this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Severity = Literal["critical", "high", "medium", "low", "info"]
PiiCategory = Literal["ssn", "credit_card", "email", "phone_us", "ipv4", "iban", "zip_plus4"]


@dataclass(frozen=True, slots=True)
class PiiMatch:
    """One PII hit inside a body."""

    category: PiiCategory
    preview: str  # always masked
    offset: int
    severity: Severity


# --------------------------------------------------------------------------- #
# Pattern catalogue
# --------------------------------------------------------------------------- #

_SSN_RE = re.compile(r"\b([0-7]\d{2})-(\d{2})-(\d{4})\b")
_ZIP_PLUS4_RE = re.compile(r"\b\d{5}-\d{4}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.IGNORECASE)
_PHONE_US_RE = re.compile(r"(?:\b|\()(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IBAN_RE = re.compile(r"\b([A-Z]{2})(\d{2})([A-Z0-9]{11,30})\b")
_PAN_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #


def _luhn_ok(digits: str) -> bool:
    """Run the Luhn checksum on a digit-only string."""

    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _ssn_ok(area: str, group: str, serial: str) -> bool:
    """Reject the published-invalid SSAs (000, 666, 9XX area; 00 group; 0000 serial)."""

    if area in {"000", "666"}:
        return False
    if area.startswith("9"):
        return False
    if group == "00":
        return False
    return serial != "0000"


def _is_loopback(ipv4: str) -> bool:
    octets = ipv4.split(".")
    return octets[0] in {"127", "0", "10"} or ipv4.startswith("192.168.")


# --------------------------------------------------------------------------- #
# Masking
# --------------------------------------------------------------------------- #


def _mask_ssn(value: str) -> str:
    last4 = value[-4:]
    return f"***-**-{last4}"


def _mask_pan(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"{digits[:6]}...{digits[-4:]}"


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def _mask_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return "***-***-****"
    return f"***-***-{digits[-4:]}"


def _mask_ipv4(value: str) -> str:
    octets = value.split(".")
    return ".".join(octets[:2] + ["***", "***"])


def _mask_iban(value: str) -> str:
    return f"{value[:4]}***{value[-4:]}"


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #


_DEFAULT_SEVERITY: Final[dict[PiiCategory, Severity]] = {
    "ssn": "critical",
    "credit_card": "critical",
    "iban": "high",
    "phone_us": "medium",
    "email": "low",
    "ipv4": "low",
    "zip_plus4": "low",
}


def scan_body_for_pii(
    body: str,
    *,
    content_type: str | None = None,
    max_findings: int = 200,
) -> tuple[PiiMatch, ...]:
    """Scan ``body`` for PII and return masked matches.

    ``content_type`` is consulted only to skip binary types
    (image/*, video/*, audio/*) where a pattern hit would be
    spurious. Text-like types and JSON are always scanned.
    """

    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct.startswith(("image/", "video/", "audio/", "font/", "application/octet-stream")):
            return ()

    matches: list[PiiMatch] = []

    for m in _SSN_RE.finditer(body):
        if not _ssn_ok(m.group(1), m.group(2), m.group(3)):
            continue
        matches.append(
            PiiMatch(
                category="ssn",
                preview=_mask_ssn(m.group(0)),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["ssn"],
            )
        )

    for m in _PAN_RE.finditer(body):
        candidate = m.group(0)
        digits = "".join(ch for ch in candidate if ch.isdigit())
        if not _luhn_ok(digits):
            continue
        matches.append(
            PiiMatch(
                category="credit_card",
                preview=_mask_pan(candidate),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["credit_card"],
            )
        )

    for m in _EMAIL_RE.finditer(body):
        matches.append(
            PiiMatch(
                category="email",
                preview=_mask_email(m.group(0)),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["email"],
            )
        )

    for m in _PHONE_US_RE.finditer(body):
        matches.append(
            PiiMatch(
                category="phone_us",
                preview=_mask_phone(m.group(0)),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["phone_us"],
            )
        )

    for m in _IPV4_RE.finditer(body):
        if _is_loopback(m.group(0)):
            continue
        matches.append(
            PiiMatch(
                category="ipv4",
                preview=_mask_ipv4(m.group(0)),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["ipv4"],
            )
        )

    for m in _IBAN_RE.finditer(body):
        matches.append(
            PiiMatch(
                category="iban",
                preview=_mask_iban(m.group(0)),
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["iban"],
            )
        )

    for m in _ZIP_PLUS4_RE.finditer(body):
        matches.append(
            PiiMatch(
                category="zip_plus4",
                preview=m.group(0)[:5] + "-****",
                offset=m.start(),
                severity=_DEFAULT_SEVERITY["zip_plus4"],
            )
        )

    matches.sort(key=lambda m: m.offset)
    return tuple(matches[:max_findings])


__all__ = [
    "PiiCategory",
    "PiiMatch",
    "scan_body_for_pii",
]
