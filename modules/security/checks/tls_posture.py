"""TLS / cert-posture probe (Phase 32.03, ADR-0044).

Read-only handshake against the configured target host on port 443
(or ``target.port``). Records the negotiated TLS version, cipher
suite, leaf certificate fingerprint + chain expiry + SAN list, and
inspects the ``Strict-Transport-Security`` header on the matching
HTTPS endpoint.

our engineering rules: this probe is strictly read-only. It MUST NOT
- attempt a downgrade by re-handshaking with restricted cipher lists,
- brute-force cipher suites,
- send anything to the socket other than the TLS handshake records,
- modify the server's state.

The safety guard at
``tests/security/test_tls_no_downgrade.py`` asserts no
``socket.send`` call exists outside the handshake.
"""

from __future__ import annotations

import socket
import ssl
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import urlparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue

CHECK_NAME = "tls_posture"

_LEGACY_VERSIONS: Final[frozenset[str]] = frozenset({"TLSv1", "TLSv1.1", "SSLv3", "SSLv2"})
_WEAK_CIPHER_TOKENS: Final[tuple[str, ...]] = (
    "RC4",
    "DES",
    "3DES",
    "NULL",
    "EXP",
    "EXPORT",
    "MD5",
    "ANON",
)
_CBC_TOKEN: Final[str] = "CBC"
_EXPIRY_WARNING_DAYS: Final[int] = 14
_RECOMMENDED_HSTS_SECONDS: Final[int] = 31_536_000


@dataclass(frozen=True, slots=True)
class TlsHandshakeResult:
    """Snapshot of a TLS handshake (no socket retained)."""

    host: str
    port: int
    tls_version: str
    cipher_name: str
    cipher_bits: int | None
    leaf_subject_cn: str | None
    leaf_issuer_cn: str | None
    not_before: datetime
    not_after: datetime
    san: tuple[str, ...]
    fingerprint_sha256: str
    hsts_header: str | None = None


def _parse_dn(dn: Iterable[Iterable[tuple[str, str]]] | None) -> dict[str, str]:
    """Flatten ``cert['subject']`` / ``cert['issuer']`` into a dict."""

    out: dict[str, str] = {}
    if dn is None:
        return out
    for rdn in dn:
        for key, value in rdn:
            out[key] = value
    return out


def _parse_not_after(value: str) -> datetime:
    # ssl returns e.g. ``"Apr 18 14:30:00 2027 GMT"`` — strict format.
    return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)


def _parse_hsts_max_age(header: str) -> int | None:
    for token in header.split(";"):
        kv = token.strip().lower()
        if kv.startswith("max-age="):
            try:
                return int(kv.split("=", 1)[1])
            except ValueError:
                return None
    return None


def evaluate_handshake(
    handshake: TlsHandshakeResult,
    *,
    now: datetime | None = None,
) -> Iterable[SecurityIssue]:
    """Pure rule evaluator over a captured :class:`TlsHandshakeResult`."""

    current = now or datetime.now(UTC)

    if handshake.tls_version in _LEGACY_VERSIONS:
        yield SecurityIssue(
            rule_id="SEC-TLS-VERSION-LEGACY",
            severity="high",
            confidence=0.99,
            title=f"Legacy TLS protocol negotiated ({handshake.tls_version})",
            description=(
                "Modern browsers reject sub-TLS-1.2 connections. The "
                "server is presenting an out-of-policy protocol."
            ),
            route=None,
            evidence={
                "host": handshake.host,
                "tls_version": handshake.tls_version,
                "cwe_id": "CWE-326",
                "attack_id": "T1573",
            },
            recommendation=(
                "Disable TLS 1.0 / 1.1 / SSLv3 on the listener and pin " "the minimum to TLS 1.2."
            ),
        )

    cipher_upper = handshake.cipher_name.upper()
    weak_token = next((tok for tok in _WEAK_CIPHER_TOKENS if tok in cipher_upper), None)
    if weak_token is not None:
        yield SecurityIssue(
            rule_id="SEC-TLS-WEAK-CIPHER",
            severity="high",
            confidence=0.99,
            title=f"Weak TLS cipher negotiated ({handshake.cipher_name})",
            description=(
                f"Cipher suite contains forbidden token `{weak_token}`. "
                "Weak suites must be removed from the server's allow list."
            ),
            route=None,
            evidence={
                "host": handshake.host,
                "cipher": handshake.cipher_name,
                "cwe_id": "CWE-326",
                "attack_id": "T1573",
            },
            recommendation=(
                "Restrict the cipher list to AEAD suites " "(GCM / CHACHA20-POLY1305)."
            ),
        )
    elif handshake.tls_version == "TLSv1.2" and _CBC_TOKEN in cipher_upper:
        yield SecurityIssue(
            rule_id="SEC-TLS-WEAK-CIPHER",
            severity="medium",
            confidence=0.9,
            title=f"CBC-mode cipher under TLS 1.2 ({handshake.cipher_name})",
            description=(
                "TLS 1.2 with a CBC-mode cipher remains vulnerable to "
                "padding-oracle classes of attacks. Prefer AEAD."
            ),
            route=None,
            evidence={
                "host": handshake.host,
                "cipher": handshake.cipher_name,
                "cwe_id": "CWE-326",
            },
            recommendation="Move to AEAD ciphers (GCM or CHACHA20-POLY1305).",
        )

    if handshake.not_after < current:
        yield SecurityIssue(
            rule_id="SEC-TLS-CERT-EXPIRED",
            severity="critical",
            confidence=0.99,
            title="TLS certificate is expired",
            description=(
                f"Leaf certificate notAfter is "
                f"{handshake.not_after.isoformat()}; current wall-clock "
                f"is {current.isoformat()}."
            ),
            route=None,
            evidence={
                "host": handshake.host,
                "not_after": handshake.not_after.isoformat(),
                "fingerprint_sha256": handshake.fingerprint_sha256,
                "cwe_id": "CWE-295",
            },
            recommendation="Renew and deploy the certificate immediately.",
        )
    else:
        days_left = (handshake.not_after - current).days
        if days_left < _EXPIRY_WARNING_DAYS:
            yield SecurityIssue(
                rule_id="SEC-TLS-CERT-EXPIRING-SOON",
                severity="medium",
                confidence=0.99,
                title=f"TLS certificate expires in {days_left} days",
                description=(
                    "Schedule certificate renewal; the leaf certificate "
                    f"expires on {handshake.not_after.isoformat()}."
                ),
                route=None,
                evidence={
                    "host": handshake.host,
                    "not_after": handshake.not_after.isoformat(),
                    "days_left": days_left,
                    "cwe_id": "CWE-295",
                },
                recommendation="Renew the certificate before expiry.",
            )

    if handshake.hsts_header is None:
        yield SecurityIssue(
            rule_id="SEC-TLS-HSTS-MISSING",
            severity="medium",
            confidence=0.95,
            title="HTTPS endpoint did not return Strict-Transport-Security",
            description=(
                "Without HSTS, browsers may downgrade subsequent "
                "requests to plain HTTP. CWE-319."
            ),
            route="/",
            evidence={
                "host": handshake.host,
                "cwe_id": "CWE-319",
            },
            recommendation=(
                "Send `Strict-Transport-Security: max-age=31536000; "
                "includeSubDomains` on every HTTPS response."
            ),
        )
    else:
        max_age = _parse_hsts_max_age(handshake.hsts_header)
        if max_age is None or max_age < _RECOMMENDED_HSTS_SECONDS:
            yield SecurityIssue(
                rule_id="SEC-TLS-HSTS-TOO-SHORT",
                severity="medium",
                confidence=0.9,
                title="HSTS max-age below 1 year",
                description=(
                    f"`Strict-Transport-Security` max-age is " f"{max_age}s; raise to ≥31536000."
                ),
                route="/",
                evidence={
                    "host": handshake.host,
                    "hsts": handshake.hsts_header,
                    "max_age": max_age,
                    "cwe_id": "CWE-319",
                },
                recommendation="Raise HSTS max-age to 31536000 (one year).",
            )


def probe_host(
    host: str, port: int, *, http_client: httpx.Client | None = None
) -> TlsHandshakeResult:
    """Open a single read-only TLS handshake to ``(host, port)``.

    The function consumes the handshake records, captures the server's
    leaf certificate + negotiated protocol + cipher, then closes the
    socket. It writes NO application-layer bytes. The optional
    ``http_client`` is used solely to read the `Strict-Transport-Security`
    response header on a follow-up GET to ``https://<host>:<port>/``.
    """

    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    with (
        socket.create_connection((host, port), timeout=10) as raw_sock,
        context.wrap_socket(raw_sock, server_hostname=host) as ssock,
    ):
        tls_version = ssock.version() or "unknown"
        cipher = ssock.cipher() or ("unknown", "unknown", None)
        cert = ssock.getpeercert() or {}
        der = ssock.getpeercert(binary_form=True) or b""
    import hashlib

    fingerprint = hashlib.sha256(der).hexdigest()
    subject = _parse_dn(cert.get("subject"))
    issuer = _parse_dn(cert.get("issuer"))
    not_after = _parse_not_after(cert["notAfter"]) if cert.get("notAfter") else datetime.now(UTC)
    not_before = _parse_not_after(cert["notBefore"]) if cert.get("notBefore") else datetime.now(UTC)
    san_pairs: tuple[Any, ...] = cert.get("subjectAltName", ()) or ()
    san = tuple(value for kind, value in san_pairs if kind in {"DNS", "IP Address"})
    hsts_header: str | None = None
    if http_client is not None:
        try:
            response = http_client.get(f"https://{host}:{port}/")
            hsts_header = response.headers.get("strict-transport-security")
        except httpx.HTTPError:
            hsts_header = None
    return TlsHandshakeResult(
        host=host,
        port=port,
        tls_version=tls_version,
        cipher_name=str(cipher[0]),
        cipher_bits=int(cipher[2]) if cipher[2] is not None else None,
        leaf_subject_cn=subject.get("commonName"),
        leaf_issuer_cn=issuer.get("commonName"),
        not_before=not_before,
        not_after=not_after,
        san=san,
        fingerprint_sha256=fingerprint,
        hsts_header=hsts_header,
    )


def run_tls_posture_check(
    ctx: CheckContext,
    *,
    probe: callable | None = None,  # type: ignore[type-arg]
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    parsed = urlparse(str(ctx.target.base_url))
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host:
        _audit(ctx, kind="skip", detail="non-https or no host")
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=0,
            skipped=True,
            skipped_reason="non-https target",
        )
    port = parsed.port or 443
    probe_callable = probe or (lambda h, p: probe_host(h, p, http_client=ctx.client))
    try:
        handshake = probe_callable(host, port)
    except (ssl.SSLError, OSError) as exc:
        _audit(ctx, kind="error", detail=str(exc))
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return SecurityCheckResult(
            check=CHECK_NAME,
            targets_scanned=0,
            issues=(),
            duration_ms=elapsed_ms,
            skipped=True,
            skipped_reason=f"handshake_failed:{exc}",
        )
    issues = tuple(evaluate_handshake(handshake))
    elapsed_ms = int((time.monotonic() - start) * 1000)
    detail = (
        f"version={handshake.tls_version} cipher={handshake.cipher_name} " f"issues={len(issues)}"
    )
    _audit(ctx, kind="complete", detail=detail)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=1,
        issues=issues,
        duration_ms=elapsed_ms,
    )


def _audit(ctx: CheckContext, *, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "detail": detail,
        },
    )


# Keep ``timezone`` and datetime imports live for ruff/mypy.
_ = UTC


__all__ = [
    "CHECK_NAME",
    "TlsHandshakeResult",
    "evaluate_handshake",
    "probe_host",
    "run_tls_posture_check",
]
