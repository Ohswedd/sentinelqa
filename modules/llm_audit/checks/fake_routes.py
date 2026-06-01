"""LLM-FAKE-ROUTE + LLM-FAKE-ENDPOINT (the documentation, task 19.03).

Two cross-reference checks:

1. Every internal link that the frontend renders or routes to must
   resolve to a route the crawler actually reached with a 2xx/3xx
   status code. Links pointing at known-404 routes get a finding.
2. Every API endpoint the frontend code references must either be in
   the observed traffic OR be declared by an ingested OpenAPI /
   GraphQL schema. References without backing get a finding.

The check is pure: it takes typed signal records and returns
``CheckFinding`` records.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from urllib.parse import urlparse

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import ApiReference, LinkReference
from modules.llm_audit.rules import LLM_FAKE_ENDPOINT, LLM_FAKE_ROUTE

_PARAM_PATTERN = re.compile(r"\[(id|uuid|hex|slug)\]", re.IGNORECASE)
_NUMERIC_SEGMENT = re.compile(r"^\d+$")
_UUID_SEGMENT = re.compile(r"^[0-9a-fA-F-]{8,}$")


def _normalize_path(value: str) -> str:
    """Pull just the path out of a URL and strip a trailing slash.

    Keep query strings off — the cross-reference compares route paths.
    """

    parsed = urlparse(value)
    path = parsed.path or value
    if path.startswith(("http://", "https://")):
        path = urlparse(path).path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path


def _path_template(path: str) -> str:
    """Replace numeric / UUID-looking segments with bracket placeholders."""

    segments = path.split("/")
    templated: list[str] = []
    for segment in segments:
        if not segment:
            templated.append(segment)
            continue
        if _UUID_SEGMENT.match(segment) and "-" in segment:
            templated.append("[uuid]")
        elif _NUMERIC_SEGMENT.match(segment):
            templated.append("[id]")
        else:
            templated.append(segment)
    return "/".join(templated)


def _match_endpoint(reference: tuple[str, str], universe: Iterable[tuple[str, str]]) -> bool:
    ref_method, ref_path = reference
    ref_template = _path_template(_normalize_path(ref_path))
    for method, path in universe:
        if method.upper() != ref_method.upper():
            continue
        candidate = _path_template(_normalize_path(path))
        if candidate == ref_template:
            return True
    return False


def check_fake_routes(
    references: Iterable[LinkReference],
    *,
    observed_routes: Iterable[str],
    observed_route_status: Mapping[str, int],
) -> tuple[CheckFinding, ...]:
    """Flag internal links pointing at routes the app does not serve."""

    ok_paths: set[str] = set()
    bad_paths: dict[str, int] = {}
    for url, status in observed_route_status.items():
        normalized = _normalize_path(url)
        if 200 <= status < 400:
            ok_paths.add(normalized)
        elif status >= 400:
            bad_paths[normalized] = status
    for url in observed_routes:
        normalized = _normalize_path(url)
        ok_paths.add(normalized)

    findings: list[CheckFinding] = []
    for reference in references:
        target = _normalize_path(reference.target_path)
        if target in ok_paths:
            continue
        if target in bad_paths:
            status = bad_paths[target]
            findings.append(
                CheckFinding(
                    rule_id=LLM_FAKE_ROUTE.id,
                    title=f"Link to {target!r} returns {status}",
                    description=(
                        f"The {reference.source} on {reference.source_route} "
                        f"links to {target!r}, but the crawler observed that "
                        f"path returning HTTP {status}."
                    ),
                    route=reference.source_route,
                    extra_context=(
                        ("target_path", target),
                        ("backend_status", str(status)),
                        ("source_kind", reference.source),
                    ),
                )
            )
            continue
        # Not observed at all — only flag when a `target_path` does not
        # appear as the prefix of an observed route. We err on the side
        # of caution; SPAs frequently render routes the crawler missed.
        if any(
            observed.startswith(target + "/") or target.startswith(observed + "/")
            for observed in ok_paths
        ):
            continue
        findings.append(
            CheckFinding(
                rule_id=LLM_FAKE_ROUTE.id,
                title=f"Link to {target!r} was never observed",
                description=(
                    f"The {reference.source} on {reference.source_route} "
                    f"links to {target!r}, but the crawler never reached "
                    "that path during discovery."
                ),
                route=reference.source_route,
                confidence_override=0.7,
                extra_context=(
                    ("target_path", target),
                    ("source_kind", reference.source),
                ),
            )
        )
    return tuple(findings)


def check_fake_endpoints(
    api_references: Iterable[ApiReference],
    *,
    observed_endpoints: Iterable[tuple[str, str]],
    openapi_endpoints: Iterable[tuple[str, str]],
) -> tuple[CheckFinding, ...]:
    """Flag API references that match neither observed traffic nor an OpenAPI entry."""

    obs = tuple(observed_endpoints)
    docs = tuple(openapi_endpoints)
    findings: list[CheckFinding] = []
    for reference in api_references:
        ref = (reference.method.upper(), _normalize_path(reference.path))
        if _match_endpoint(ref, obs):
            continue
        if _match_endpoint(ref, docs):
            continue
        findings.append(
            CheckFinding(
                rule_id=LLM_FAKE_ENDPOINT.id,
                title=f"Frontend references {reference.method.upper()} {ref[1]}",
                description=(
                    f"The frontend code at {reference.source_file or 'unknown'} "
                    f"references {reference.method.upper()} {ref[1]}, but neither "
                    "the crawler nor the ingested OpenAPI / GraphQL schema "
                    "lists that endpoint."
                ),
                file=reference.source_file,
                extra_context=(
                    ("endpoint", f"{reference.method.upper()} {ref[1]}"),
                    ("source_file", reference.source_file or "unknown"),
                ),
            )
        )
    return tuple(findings)


__all__ = [
    "check_fake_routes",
    "check_fake_endpoints",
    "_normalize_path",
    "_path_template",
]
