# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""HTTP/2 + HTTP/3 negotiation probe (v1.3.0).

Audits today inspect headers but never the transport. This module
records ALPN, HTTP/2, and HTTP/3 availability for a target host.

Pure helpers in this module — no network IO. Tests feed synthetic
probe results; the production probe (httpx + a future ``hypercorn``
HTTP/3 client) lives outside the module.

Two outputs:

* :func:`evaluate_protocol_probe` — given a captured
  :class:`ProtocolProbeResult`, return a list of
  :class:`ProtocolFinding` records (each with severity + rationale).
* :func:`grade_protocol_support` — a compact ``"A+"``-style grade
  the report module can render in a badge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True, slots=True)
class ProtocolProbeResult:
    """Outcome of a single host probe."""

    host: str
    is_https: bool
    alpn_offered: tuple[str, ...] = field(default_factory=tuple)
    alpn_negotiated: str | None = None
    http2_supported: bool = False
    http3_supported: bool = False
    alt_svc_header: str | None = None


@dataclass(frozen=True, slots=True)
class ProtocolFinding:
    """One observation about transport-protocol coverage."""

    code: str
    severity: Severity
    title: str
    description: str


_GRADES = ("A+", "A", "B", "C", "D", "F")


def evaluate_protocol_probe(probe: ProtocolProbeResult) -> tuple[ProtocolFinding, ...]:
    """Return one finding per gap detected in the probe."""

    if not probe.is_https:
        return (
            ProtocolFinding(
                code="PROTO-NO-HTTPS",
                severity="high",
                title=f"{probe.host}: TLS unavailable",
                description=(
                    "Target is served over HTTP. HTTP/2 and HTTP/3 "
                    "require TLS in every shipping browser; falling back "
                    "to HTTP/1.1 cleartext blocks the upgrade entirely."
                ),
            ),
        )

    findings: list[ProtocolFinding] = []
    if not probe.http2_supported:
        findings.append(
            ProtocolFinding(
                code="PROTO-NO-H2",
                severity="medium",
                title=f"{probe.host}: HTTP/2 not negotiated",
                description=(
                    "ALPN offered "
                    f"{probe.alpn_offered or ('h2', 'http/1.1')!r} but "
                    "the negotiated protocol was "
                    f"{probe.alpn_negotiated or 'http/1.1'!r}. "
                    "HTTP/2 reduces head-of-line blocking and is "
                    "expected for production traffic."
                ),
            )
        )

    if not probe.http3_supported:
        findings.append(
            ProtocolFinding(
                code="PROTO-NO-H3",
                severity="low",
                title=f"{probe.host}: HTTP/3 not advertised",
                description=(
                    "No ``Alt-Svc: h3=...`` header was observed. "
                    "HTTP/3 (QUIC) improves connection setup on mobile "
                    "links and is now broadly supported by Chrome, "
                    "Edge, Firefox, and Safari."
                ),
            )
        )

    if probe.alt_svc_header and "h3" not in probe.alt_svc_header.lower():
        findings.append(
            ProtocolFinding(
                code="PROTO-ALT-SVC-NO-H3",
                severity="info",
                title=f"{probe.host}: Alt-Svc present but does not advertise h3",
                description=(
                    "Alt-Svc header was emitted but contains no "
                    "``h3=...`` entry. If HTTP/3 is enabled, the "
                    "advertisement must be present so clients upgrade."
                ),
            )
        )
    return tuple(findings)


def grade_protocol_support(probe: ProtocolProbeResult) -> str:
    """Return a compact letter grade for the transport posture.

    A+ is reserved for full HTTPS + HTTP/2 + HTTP/3 + Alt-Svc.
    """

    if not probe.is_https:
        return "F"
    if probe.http2_supported and probe.http3_supported:
        if probe.alt_svc_header and "h3" in probe.alt_svc_header.lower():
            return "A+"
        return "A"
    if probe.http2_supported:
        return "B"
    return "C"


__all__ = [
    "ProtocolFinding",
    "ProtocolProbeResult",
    "evaluate_protocol_probe",
    "grade_protocol_support",
]
