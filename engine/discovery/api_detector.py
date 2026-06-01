"""API endpoint detection.

The HTTP-first release can't observe live XHR/fetch traffic — that requires a
browser. Instead the detector:

1. Scans inline ``<script>`` bodies and fetched external JS bundles for
 string literals that look like API paths.
2. Walks every crawled HTML page for ``<form action>`` URLs and treats them
 as POST endpoints.
3. Walks every crawled URL: any path matching ``/api/`` or returning
 ``application/json`` is treated as an observed endpoint.
4. Templates parameterized paths (numeric IDs, UUIDs, slugs) into stable
 identifiers like ``/api/users/[id]``.
5. Cross-checks references-vs-observations to flag suspicious patterns:
 referenced in JS but never called during crawling (likely missing /
 broken handler — LLM-audit signal).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urljoin, urlparse

from pydantic import ValidationError

from engine.discovery.crawler import CrawlResult
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.ids import IdGenerator
from engine.domain.route import HttpMethod

# Match string literals that look like API paths.
# - Single or double quoted.
# - Start with `/` (absolute path) or `/api`.
# - Contain alphanumerics, dashes, slashes, brackets, dots, underscores, colons.
_PATH_PATTERN = re.compile(r"""(?P<quote>['"`])(?P<path>/[a-zA-Z0-9_\-./:\[\]{}]{1,200})\1""")

# Path-parameter heuristics: numeric IDs, UUIDs, hex IDs, slugs that look
# auto-generated. Anything else is treated as a literal segment.
_NUMERIC_PATTERN = re.compile(r"^\d+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{16,}$")


SuspicionKind = Literal["referenced_only", "observed_5xx", "mock_data_smell", "undocumented"]


@dataclass(frozen=True)
class ApiSuspicion:
    """A heuristic flag the risk model lifts into the RiskMap."""

    endpoint_path: str
    kind: SuspicionKind
    detail: str


@dataclass(frozen=True)
class ApiDetectorResult:
    """Output of :meth:`ApiDetector.detect`."""

    endpoints: tuple[ApiEndpoint, ...] = field(default_factory=tuple)
    referenced_only_paths: tuple[str, ...] = field(default_factory=tuple)
    observed_5xx_paths: tuple[str, ...] = field(default_factory=tuple)
    suspicions: tuple[ApiSuspicion, ...] = field(default_factory=tuple)


def template_path(path: str) -> str:
    """Replace parameterized segments with ``[id]`` / ``[uuid]`` / ``[slug]``.

    Pure function so tests can pin every parameter heuristic.
    """

    parsed = urlparse(path)
    raw_path = parsed.path or "/"
    segments = raw_path.split("/")
    templated: list[str] = []
    for segment in segments:
        if not segment:
            templated.append(segment)
            continue
        if _UUID_PATTERN.match(segment):
            templated.append("[uuid]")
        elif _NUMERIC_PATTERN.match(segment):
            templated.append("[id]")
        elif _HEX_PATTERN.match(segment):
            templated.append("[hex]")
        else:
            templated.append(segment)
    out = "/".join(templated)
    if parsed.query:
        return f"{out}?{parsed.query}"
    return out


class ApiDetector:
    """Build :class:`ApiEndpoint` records from a crawl result + JS bodies."""

    def __init__(self, id_generator: IdGenerator | None = None) -> None:
        self._ids = id_generator or IdGenerator()

    def detect(
        self,
        crawl: CrawlResult,
        *,
        js_bodies: Mapping[str, str] | None = None,
    ) -> ApiDetectorResult:
        from bs4 import BeautifulSoup, Tag

        endpoints: dict[tuple[HttpMethod, str], ApiEndpoint] = {}
        observed_5xx: set[str] = set()
        referenced_paths: set[str] = set()

        # 1) Observed traffic — every crawled URL is itself an endpoint.
        for page in crawl.pages:
            templated = template_path(page.url)
            self._record_endpoint(endpoints, method="GET", path=templated)
            if 500 <= page.status_code < 600:
                observed_5xx.add(templated)

            # 2) Forms — every form action is a POST/PUT/etc. endpoint.
            soup = BeautifulSoup(page.html, "lxml")
            for tag in soup.find_all("form"):
                if not isinstance(tag, Tag):
                    continue
                action = tag.get("action")
                if not isinstance(action, str) or not action.strip():
                    continue
                method_attr = tag.get("method")
                method = self._resolve_method(method_attr)
                absolute = urljoin(page.url, action)
                self._record_endpoint(endpoints, method=method, path=template_path(absolute))

        # 3) References from JS bundles + inline scripts.
        inline_bodies = self._collect_inline(crawl)
        all_bodies = {**(js_bodies or {}), **inline_bodies}
        for body in all_bodies.values():
            for match in _PATH_PATTERN.finditer(body):
                raw_path = match.group("path")
                if raw_path.startswith("//"):  # protocol-relative URL — skip.
                    continue
                if not self._looks_like_api(raw_path):
                    continue
                templated = template_path(raw_path)
                referenced_paths.add(templated)

        observed_paths = {ep.path for ep in endpoints.values()}
        referenced_only = sorted(p for p in referenced_paths if p not in observed_paths)
        for path in referenced_only:
            self._record_endpoint(endpoints, method="GET", path=path)

        # 4) Suspicions — collect and emit signed records.
        suspicions: list[ApiSuspicion] = []
        for path in referenced_only:
            suspicions.append(
                ApiSuspicion(
                    endpoint_path=path,
                    kind="referenced_only",
                    detail="path string seen in JS but never reached during the crawl",
                )
            )
        for path in sorted(observed_5xx):
            suspicions.append(
                ApiSuspicion(
                    endpoint_path=path,
                    kind="observed_5xx",
                    detail="endpoint returned a 5xx status during discovery",
                )
            )

        return ApiDetectorResult(
            endpoints=tuple(endpoints.values()),
            referenced_only_paths=tuple(referenced_only),
            observed_5xx_paths=tuple(sorted(observed_5xx)),
            suspicions=tuple(suspicions),
        )

    def _record_endpoint(
        self,
        endpoints: dict[tuple[HttpMethod, str], ApiEndpoint],
        *,
        method: HttpMethod,
        path: str,
    ) -> None:
        # Truncate at the domain field limit so we never trip the validator.
        path = path[:2048]
        key = (method, path)
        if key in endpoints:
            return
        try:
            endpoint = ApiEndpoint(
                id=self._ids.new("API"),
                method=method,
                path=path,
                source="discovered",
            )
        except ValidationError:
            return
        endpoints[key] = endpoint

    def _resolve_method(self, value: object) -> HttpMethod:
        if not isinstance(value, str) or not value:
            return "POST"
        upper = value.upper()
        if upper in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            return upper  # type: ignore[return-value]
        return "POST"

    def _looks_like_api(self, path: str) -> bool:
        if not path.startswith("/"):
            return False
        if path.endswith(
            (
                ".css",
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".webp",
                ".ico",
                ".woff",
                ".woff2",
                ".js",
                ".map",
            )
        ):
            return False
        return not path.startswith(("/static/", "/assets/", "/_next/", "/build/"))

    def _collect_inline(self, crawl: CrawlResult) -> dict[str, str]:
        bodies: dict[str, str] = {}
        for index, page in enumerate(crawl.pages):
            for inline_index, body in enumerate(page.inline_scripts):
                if body.strip():
                    bodies[f"{page.url}#inline-{index}-{inline_index}"] = body
        return bodies


def detect_api_endpoints(
    crawl: CrawlResult,
    *,
    js_bodies: Mapping[str, str] | None = None,
) -> ApiDetectorResult:
    """Convenience free-function wrapper used by the pipeline."""

    return ApiDetector().detect(crawl, js_bodies=js_bodies)


def endpoint_paths(endpoints: Iterable[ApiEndpoint]) -> set[str]:
    return {ep.path for ep in endpoints}


__all__ = [
    "ApiDetector",
    "ApiDetectorResult",
    "ApiSuspicion",
    "SuspicionKind",
    "detect_api_endpoints",
    "endpoint_paths",
    "template_path",
]
