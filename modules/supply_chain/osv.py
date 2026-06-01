"""OSV vulnerability lookup.

Reads the SBOM produced by :mod:`modules.supply_chain.sbom` and queries
the public OSV API (https://api.osv.dev) via ``POST /v1/querybatch``.
The lookup is read-only: we send package + version + ecosystem and
parse the advisories that come back. The OSV response carries vendor
references and CVE / GHSA ids only; we do NOT carry through any exploit
payloads or proof-of-concept code.

Offline degradation is mandatory. The README is explicit:
"Offline degradation is ``skipped``, not ``errored``, not ``passed``."
A network failure here means the supply-chain run records
:class:`OsvReport.skipped=True` with a short reason; the rest of the
run continues.

A token-bucket rate-limit (default 5 req/s) protects ``api.osv.dev``
from over-eager runs even though we batch up to 1 000 queries per call.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

import httpx
from engine.domain.finding import Severity

from modules.supply_chain.models import (
    Ecosystem,
    OsvAdvisory,
    OsvComponentResult,
    OsvReport,
    SbomComponent,
    SbomDocument,
)

OSV_API_BASE: Final[str] = "https://api.osv.dev"
OSV_BATCH_ENDPOINT: Final[str] = "/v1/querybatch"
OSV_MAX_PER_BATCH: Final[int] = 1000
"""OSV's documented per-call cap (https://google.github.io/osv.dev/post-v1-querybatch/)."""


@dataclass(frozen=True, slots=True)
class _RateLimiter:
    """Simple token-bucket so we never exceed ``rate_limit_rps``.

    We don't need precise scheduling — the goal is to avoid hammering
    ``api.osv.dev`` if a fleet of components is queued. The bucket
    drains in real time and refills at ``rate_limit_rps`` tokens/sec
    with a single-token capacity (one request per ``1/rate`` seconds).
    """

    rate_limit_rps: float

    def sleep_for(self, last_request_at: float) -> float:
        """Return seconds to sleep before the next request (>= 0)."""

        if self.rate_limit_rps <= 0:
            return 0.0
        interval = 1.0 / self.rate_limit_rps
        elapsed = max(0.0, time.monotonic() - last_request_at)
        return max(0.0, interval - elapsed)


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


def severity_from_cvss(cvss_score: float | None) -> Severity:
    """Map a CVSS v3 base score to a SentinelQA severity.

    CVSS bands per https://nvd.nist.gov/vuln-metrics/cvss:

    - 9.0..10.0 → critical
    - 7.0..8.9 → high
    - 4.0..6.9 → medium
    - 0.1..3.9 → low
    - 0.0 → info (treated as a defensive note)
    """

    if cvss_score is None:
        return "medium"
    if cvss_score >= 9.0:
        return "critical"
    if cvss_score >= 7.0:
        return "high"
    if cvss_score >= 4.0:
        return "medium"
    if cvss_score > 0.0:
        return "low"
    return "info"


def _extract_cvss(severity_entries: Sequence[Mapping[str, Any]] | None) -> float | None:
    """Pull the highest CVSS base score from OSV's ``severity`` array.

    OSV's schema (https://ossf.github.io/osv-schema/) records severity
    as ``[{type: "CVSS_V3", score: "CVSS:3.1/.../..."}]``. The score
    string carries the CVSS vector — the actual numeric base score is
    derived offline. Since we don't ship a CVSS-vector parser, we
    accept either a numeric ``score`` field (used by some OSV mirrors)
    or fall back to the vector's leading ``score=`` token.
    """

    if not severity_entries:
        return None
    best: float | None = None
    for entry in severity_entries:
        raw = entry.get("score")
        score = _coerce_cvss(raw)
        if score is None:
            continue
        if best is None or score > best:
            best = score
    return best


def _coerce_cvss(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    if isinstance(raw, str):
        # Numeric string.
        try:
            return float(raw)
        except ValueError:
            pass
        # Vector string ``CVSS:3.1/AV:N/...`` — no base score embedded,
        # so we return None and let the caller default to ``medium``.
        if raw.startswith("CVSS:"):
            return None
    return None


def _extract_cwes(database_specific: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not database_specific:
        return ()
    cwes = database_specific.get("cwe_ids")
    if isinstance(cwes, list):
        return tuple(c for c in cwes if isinstance(c, str) and c.startswith("CWE-"))
    return ()


def _extract_fixed_in(affected: Sequence[Mapping[str, Any]] | None) -> str | None:
    """Best-effort: pick the first ``fixed`` event across all ``ranges``."""

    if not affected:
        return None
    for entry in affected:
        for rng in entry.get("ranges", []) or []:
            for event in rng.get("events", []) or []:
                fixed = event.get("fixed")
                if isinstance(fixed, str) and fixed:
                    return fixed
    return None


def parse_osv_response_for_component(
    component: SbomComponent,
    vulns: Sequence[Mapping[str, Any]],
) -> OsvComponentResult:
    """Translate one OSV response entry into our wire format."""

    advisories: list[OsvAdvisory] = []
    for vuln in vulns:
        vuln_id = vuln.get("id")
        if not isinstance(vuln_id, str):
            continue
        cvss = _extract_cvss(vuln.get("severity"))
        severity = severity_from_cvss(cvss)
        advisories.append(
            OsvAdvisory(
                id=vuln_id,
                severity=severity,
                cwe_ids=_extract_cwes(vuln.get("database_specific")),
                fixed_in=_extract_fixed_in(vuln.get("affected")),
                summary=str(vuln.get("summary") or vuln.get("details") or "")[:2000],
            )
        )
    return OsvComponentResult(
        package=component.name,
        version=component.version,
        ecosystem=component.ecosystem,
        advisories=tuple(advisories),
    )


# ---------------------------------------------------------------------------
# HTTP query
# ---------------------------------------------------------------------------


def _ecosystem_label(ecosystem: Ecosystem) -> str:
    """Map our enum to OSV's documented ecosystem labels.

    OSV uses ``PyPI`` and ``npm`` verbatim — see https://ossf.github.io/
    osv-schema/#affectedpackage-field. We keep our enum aligned with
    those so the cast is a no-op, but the indirection keeps the call
    site readable.
    """

    return ecosystem


def _chunks(items: Sequence[SbomComponent], size: int) -> Iterable[Sequence[SbomComponent]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _query_payload(components: Sequence[SbomComponent]) -> dict[str, Any]:
    return {
        "queries": [
            {
                "package": {
                    "name": c.name,
                    "ecosystem": _ecosystem_label(c.ecosystem),
                },
                "version": c.version,
            }
            for c in components
        ]
    }


async def _query_batch_async(
    client: httpx.AsyncClient,
    components: Sequence[SbomComponent],
    *,
    api_base: str,
) -> Sequence[Mapping[str, Any]]:
    """POST one batch (<= 1000 entries) to OSV; return the ``results`` array."""

    response = await client.post(api_base + OSV_BATCH_ENDPOINT, json=_query_payload(components))
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        return ()
    results = body.get("results")
    if not isinstance(results, list):
        return ()
    return results


def query_osv(
    *,
    components: Sequence[SbomComponent],
    api_base: str = OSV_API_BASE,
    rate_limit_rps: float = 5.0,
    request_timeout_seconds: float = 30.0,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> OsvReport:
    """Query OSV for every component in ``components``.

    The function is synchronous so it composes with the rest of the
    module (which runs in the orchestrator's main thread). It
    drives an ``AsyncClient`` internally so the offline path can short-
    circuit on the first ``httpx.RequestError`` without needing thread
    juggling.

    The caller is responsible for filtering ``components`` down to the
    set that should hit the network — see
    :func:`run_osv_lookup_from_sbom`.
    """

    timestamp = now or datetime.now(UTC)
    if not components:
        return OsvReport(
            queried_at=timestamp,
            components_count=0,
            vulnerabilities=(),
        )

    rate_limiter = _RateLimiter(rate_limit_rps=rate_limit_rps)

    async def _run() -> OsvReport:
        nonlocal timestamp
        client_kwargs: dict[str, Any] = {
            "base_url": api_base,
            "timeout": request_timeout_seconds,
            "headers": {"user-agent": "SentinelQA/supply-chain (+https://sentinelqa.dev)"},
        }
        if transport is not None:
            client_kwargs["transport"] = transport
        last_request_at = 0.0
        async with httpx.AsyncClient(**client_kwargs) as client:
            vulnerabilities: list[OsvComponentResult] = []
            for batch in _chunks(list(components), OSV_MAX_PER_BATCH):
                sleep_for = rate_limiter.sleep_for(last_request_at)
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                last_request_at = time.monotonic()
                try:
                    batch_results = await _query_batch_async(client, batch, api_base=api_base)
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    return OsvReport(
                        queried_at=timestamp,
                        components_count=len(components),
                        vulnerabilities=tuple(vulnerabilities),
                        skipped=True,
                        skipped_reason=f"OSV unreachable: {type(exc).__name__}: {exc}"[:2000],
                    )
                for component, entry in zip(batch, batch_results, strict=False):
                    vulns = entry.get("vulns") if isinstance(entry, dict) else None
                    if not isinstance(vulns, list) or not vulns:
                        continue
                    parsed = parse_osv_response_for_component(component, vulns)
                    if parsed.advisories:
                        vulnerabilities.append(parsed)
        return OsvReport(
            queried_at=timestamp,
            components_count=len(components),
            vulnerabilities=tuple(vulnerabilities),
        )

    try:
        # We always have a fresh event loop in the orchestrator's sync
        # context; ``asyncio.run`` is fine here.
        return asyncio.run(_run())
    except RuntimeError:
        # If a caller already drives an event loop (e.g. notebooks),
        # fall back to creating a private one rather than crashing.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            with contextlib.suppress(Exception):
                loop.close()


# ---------------------------------------------------------------------------
# High-level entrypoint
# ---------------------------------------------------------------------------


def run_osv_lookup_from_sbom(
    *,
    sbom: SbomDocument,
    api_base: str = OSV_API_BASE,
    rate_limit_rps: float = 5.0,
    enabled: bool = True,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> OsvReport:
    """Query OSV for every distinct component in an SBOM.

    When ``enabled=False`` the function returns an explicitly-skipped
    :class:`OsvReport` so the audit log records that the operator opted
    out (as opposed to a network failure).
    """

    timestamp = now or datetime.now(UTC)
    if not enabled:
        return OsvReport(
            queried_at=timestamp,
            components_count=0,
            vulnerabilities=(),
            skipped=True,
            skipped_reason="policy.supply_chain.osv.enabled is false",
        )

    seen: set[tuple[str, str, str]] = set()
    flattened: list[SbomComponent] = []
    for lockfile in sbom.lockfiles:
        for c in lockfile.components:
            key = (c.ecosystem, c.name.lower(), c.version)
            if key in seen:
                continue
            seen.add(key)
            flattened.append(c)

    return query_osv(
        components=flattened,
        api_base=api_base,
        rate_limit_rps=rate_limit_rps,
        transport=transport,
        now=timestamp,
    )


def serialize_osv_report(report: OsvReport) -> dict[str, Any]:
    """Serialize the OSV report for ``vulnerabilities.json`` (sorted keys)."""

    payload: dict[str, Any] = json.loads(json.dumps(report.model_dump(mode="json"), sort_keys=True))
    return payload


__all__ = [
    "OSV_API_BASE",
    "OSV_BATCH_ENDPOINT",
    "OSV_MAX_PER_BATCH",
    "parse_osv_response_for_component",
    "query_osv",
    "run_osv_lookup_from_sbom",
    "serialize_osv_report",
    "severity_from_cvss",
]
