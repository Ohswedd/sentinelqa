"""Safety policy enforcement (our product spec, §23; our engineering rules, §26).

Every module that talks to a target MUST call :func:`SafetyPolicy.enforce`
before issuing any I/O. The policy resolves the host from
``target.base_url`` (and the host being audited if it differs), checks
allowlist membership, classifies the mode, and either returns a
:class:`SafetyDecision` (allowed) or raises a subclass of
:class:`engine.errors.base.UnsafeTargetError` (blocked).

Decisions are also appended to the run's audit log via
:func:`engine.policy.audit_log.write_audit_entry` so an investigator can
reconstruct exactly what SentinelQA refused to scan.
"""

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pydantic import Field

from engine.domain.base import SentinelModel
from engine.domain.schema import CONFIG_SCHEMA_VERSION
from engine.domain.target import Mode, Target
from engine.errors.base import UnknownHostError
from engine.policy.audit_log import write_audit_entry
from engine.policy.proof_of_authorization import ProofOfAuthorization, require_proof

# Loopback names treated as local even without an IP form.
_LOCAL_HOSTS = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})


def _normalize_host(value: str) -> str:
    """Lowercase and strip an optional port.

    Handles three input shapes safely:

    - Bracketed IPv6 with port (``[::1]:3000``): drop brackets and port.
    - Bare IPv6 (two or more colons, e.g. ``::1`` or ``fe80::1``): leave
      the address alone — there is no ``host:port`` ambiguity here because
      a bare IPv6 with a port is not valid URL syntax.
    - IPv4/hostname (single colon followed by digits): drop the port.
    """

    cleaned = value.strip().lower()
    if cleaned.startswith("[") and "]" in cleaned:
        return cleaned[1 : cleaned.index("]")]
    # Two or more colons → IPv6, no port to strip.
    if cleaned.count(":") >= 2:
        return cleaned
    if ":" in cleaned:
        head, _, tail = cleaned.rsplit(":", 1)[0], None, cleaned.rsplit(":", 1)[1]
        if tail.isdigit():
            cleaned = head
    return cleaned


def is_local(host: str) -> bool:
    """Return True if ``host`` is loopback or RFC1918/ULA."""

    name = _normalize_host(host)
    if name in _LOCAL_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return False
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local)


class SafetyDecision(SentinelModel):
    """Outcome of a policy check."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    allowed: bool
    reason: str = Field(min_length=1, max_length=2000)
    host: str = Field(min_length=1, max_length=512)
    mode: Mode
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    decided_at: datetime


class SafetyPolicy:
    """Stateless policy engine."""

    def enforce(
        self,
        target: Target,
        requested_mode: Mode | None = None,
        *,
        audit_log_path: Path | None = None,
        now: datetime | None = None,
    ) -> SafetyDecision:
        """Evaluate ``target`` against the safety boundary.

        Returns a :class:`SafetyDecision` when access is allowed; raises an
        :class:`engine.errors.base.UnsafeTargetError` subclass otherwise.

        ``audit_log_path``, if provided, receives one JSON line per
        decision (allowed or refused). Refusals also raise; the line lands
        before the exception propagates.
        """

        decided = (now or datetime.now(UTC)).astimezone(UTC)
        mode = requested_mode or target.mode

        url_host = self._extract_host(str(target.base_url))
        evidence: list[str] = [f"base_url_host={url_host}", f"mode={mode}"]

        local = is_local(url_host)
        allowlisted = self._is_allowlisted(url_host, target.allowed_hosts)

        if not local and not allowlisted:
            decision = SafetyDecision(
                allowed=False,
                reason=(f"Host {url_host!r} is not in target.allowed_hosts and is not local."),
                host=url_host,
                mode=mode,
                evidence=(*evidence, "check=allowlist", "result=deny"),
                decided_at=decided,
            )
            if audit_log_path is not None:
                write_audit_entry(audit_log_path, decision.to_dict())
            raise UnknownHostError(
                host=url_host,
                technical_context={
                    "host": url_host,
                    "mode": mode,
                    "allowed_hosts": sorted(target.allowed_hosts),
                },
            )

        if mode == "authorized_destructive":
            # Destructive mode against ANY host (even local) requires a
            # proof-of-authorization. This is intentionally stricter than
            # the absolute minimum the safety spec asks for — destructive
            # tests are dangerous in development too (e.g. they can wipe a
            # dev DB), so a paper trail is mandatory.
            proof: ProofOfAuthorization = require_proof(
                target.proof_of_authorization,
                host=url_host,
                capability="destructive",
            )
            evidence.append(f"proof_actor={proof.actor}")
            evidence.append(f"proof_expires_at={proof.expires_at.isoformat()}")

        decision = SafetyDecision(
            allowed=True,
            reason=(
                "Local target allowed in safe mode."
                if local and mode == "safe"
                else (
                    "Allowlisted host allowed in safe mode."
                    if mode == "safe"
                    else "Destructive mode allowed with valid proof-of-authorization."
                )
            ),
            host=url_host,
            mode=mode,
            evidence=(*evidence, "result=allow"),
            decided_at=decided,
        )
        if audit_log_path is not None:
            write_audit_entry(audit_log_path, decision.to_dict())
        return decision

    def requires_proof_of_authorization(self, target: Target, mode: Mode) -> bool:
        """True if calling :meth:`enforce` with this combo would require proof."""

        return mode == "authorized_destructive"

    def _extract_host(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.hostname:
            raise UnknownHostError(
                host=url,
                technical_context={"reason": "missing hostname", "url": url},
            )
        return _normalize_host(parsed.hostname)

    def _is_allowlisted(self, host: str, allowed: frozenset[str]) -> bool:
        normalized = _normalize_host(host)
        return any(_normalize_host(h) == normalized for h in allowed)


__all__ = ["SafetyPolicy", "SafetyDecision", "is_local"]
