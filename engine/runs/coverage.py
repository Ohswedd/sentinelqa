# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Coverage-gap detection over a completed run + its discovery output.

Walks ``discovery.json`` (routes, forms, API endpoints) and the
plan / module-result artifacts to identify surface area the run did
not exercise. The ranking gives the agent a triage list ordered by
risk.

The risk score is intentionally simple:

* routes carrying auth (``auth_required: true``) start at risk 4.
* forms with ``contains_credentials`` or POST methods start at 4.
* API endpoints that mutate (POST/PUT/PATCH/DELETE) start at 3.
* read-only GETs start at 1.

The route is upgraded by +1 when it's listed in the risk-map's
``hot_paths`` and downgraded by -1 when it's marked
``static_asset``. Final score is clamped to ``[1, 5]``.

The helpers are pure: tests feed synthetic discovery payloads and
assert on the ranked output.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

GapKind = Literal["route", "form", "api_endpoint"]


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """One uncovered surface element."""

    kind: GapKind
    identifier: str  # path, form-id, or "METHOD path"
    risk_score: int  # 1..5
    rationale: str


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """A ranked coverage-gap report."""

    gaps: tuple[CoverageGap, ...] = field(default_factory=tuple)
    discovered_total: int = 0
    covered_total: int = 0

    @property
    def coverage_ratio(self) -> float:
        if self.discovered_total == 0:
            return 1.0
        return self.covered_total / self.discovered_total


def _route_risk(route: dict[str, Any]) -> int:
    base = 4 if route.get("auth_required") else 2
    if route.get("hot_path"):
        base += 1
    if route.get("static_asset"):
        base -= 1
    return max(1, min(base, 5))


def _form_risk(form: dict[str, Any]) -> int:
    if form.get("contains_credentials") or (form.get("method", "GET").upper() != "GET"):
        return 4
    return 2


def _endpoint_risk(endpoint: dict[str, Any]) -> int:
    method = endpoint.get("method", "GET").upper()
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return 3
    return 1


def _matches(identifier: str, covered: Iterable[str]) -> bool:
    return identifier in set(covered)


def find_coverage_gaps(
    discovery_payload: dict[str, Any],
    *,
    covered_routes: Iterable[str] = (),
    covered_forms: Iterable[str] = (),
    covered_api_endpoints: Iterable[str] = (),
) -> CoverageReport:
    """Cross-reference discovery against the covered sets."""

    routes_raw = (
        discovery_payload.get("graph", {}).get("routes") or discovery_payload.get("routes") or []
    )
    forms_raw = discovery_payload.get("forms") or []
    endpoints_raw = (
        discovery_payload.get("api_endpoints") or discovery_payload.get("endpoints") or []
    )

    covered_routes_set = set(covered_routes)
    covered_forms_set = set(covered_forms)
    covered_endpoints_set = set(covered_api_endpoints)

    gaps: list[CoverageGap] = []
    discovered = 0
    covered = 0

    for route in routes_raw:
        if not isinstance(route, dict):
            continue
        path = str(route.get("path") or route.get("url") or "")
        if not path:
            continue
        discovered += 1
        if _matches(path, covered_routes_set):
            covered += 1
            continue
        risk = _route_risk(route)
        rationale = "auth-protected route" if route.get("auth_required") else "public route"
        if route.get("hot_path"):
            rationale += "; on the hot-path risk list"
        gaps.append(
            CoverageGap(kind="route", identifier=path, risk_score=risk, rationale=rationale)
        )

    for form in forms_raw:
        if not isinstance(form, dict):
            continue
        identifier = str(form.get("id") or form.get("action") or "")
        if not identifier:
            continue
        discovered += 1
        if _matches(identifier, covered_forms_set):
            covered += 1
            continue
        risk = _form_risk(form)
        rationale = (
            "credentials form"
            if form.get("contains_credentials")
            else f"{form.get('method', 'GET').upper()} form"
        )
        gaps.append(
            CoverageGap(kind="form", identifier=identifier, risk_score=risk, rationale=rationale)
        )

    for endpoint in endpoints_raw:
        if not isinstance(endpoint, dict):
            continue
        method = str(endpoint.get("method") or "GET").upper()
        path = str(endpoint.get("path") or endpoint.get("url") or "")
        if not path:
            continue
        identifier = f"{method} {path}"
        discovered += 1
        if _matches(identifier, covered_endpoints_set):
            covered += 1
            continue
        risk = _endpoint_risk(endpoint)
        rationale = (
            "mutating endpoint without coverage"
            if method != "GET"
            else "read endpoint without coverage"
        )
        gaps.append(
            CoverageGap(
                kind="api_endpoint",
                identifier=identifier,
                risk_score=risk,
                rationale=rationale,
            )
        )

    gaps.sort(key=lambda g: (-g.risk_score, g.kind, g.identifier))
    return CoverageReport(
        gaps=tuple(gaps),
        discovered_total=discovered,
        covered_total=covered,
    )


__all__ = ["CoverageGap", "CoverageReport", "find_coverage_gaps"]
