"""OpenAPI ingestion.

Reads an OpenAPI 3.0 / 3.1 document (file path or URL) and turns each
operation into an :class:`ApiEndpoint` with ``source="openapi"``. Cross-
checks against discovered endpoints to flag undocumented + expected-but-
not-observed paths.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from openapi_spec_validator import validate as validate_openapi
from openapi_spec_validator.versions.exceptions import OpenAPIVersionNotFound
from pydantic import ValidationError

from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.ids import IdGenerator
from engine.domain.route import HttpMethod

# OpenAPI methods we map back to our HttpMethod literal.
_METHODS: dict[str, HttpMethod] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "head": "HEAD",
    "options": "OPTIONS",
}


@dataclass(frozen=True)
class OpenAPICrossCheck:
    """Cross-check verdicts the pipeline persists alongside ingested endpoints."""

    undocumented_paths: tuple[str, ...] = field(default_factory=tuple)
    expected_but_not_observed: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OpenAPIIngestResult:
    """Output of :meth:`OpenAPIIngester.ingest`."""

    endpoints: tuple[ApiEndpoint, ...] = field(default_factory=tuple)
    cross_check: OpenAPICrossCheck = field(default_factory=OpenAPICrossCheck)
    title: str | None = None
    version: str | None = None


class OpenAPIIngester:
    """Pure-Python OpenAPI 3.x ingester."""

    def __init__(self, id_generator: IdGenerator | None = None) -> None:
        self._ids = id_generator or IdGenerator()

    def ingest(
        self,
        *,
        path: Path | None = None,
        url: str | None = None,
        http: httpx.Client | None = None,
    ) -> OpenAPIIngestResult:
        if path is None and url is None:
            return OpenAPIIngestResult()
        spec = self._load(path=path, url=url, http=http)
        try:
            validate_openapi(spec)  # type: ignore[arg-type]
        except OpenAPIVersionNotFound as exc:
            raise ValueError(
                "Document is not a recognized OpenAPI 3.x spec. Use a Swagger "
                "2.0 → 3.0 converter before ingestion."
            ) from exc

        endpoints: list[ApiEndpoint] = []
        for path_template, operations in (spec.get("paths") or {}).items():
            if not isinstance(operations, dict):
                continue
            for method_name, op in operations.items():
                http_method = _METHODS.get(method_name.lower())
                if http_method is None or not isinstance(op, dict):
                    continue
                try:
                    endpoints.append(
                        ApiEndpoint(
                            id=self._ids.new("API"),
                            method=http_method,
                            path=path_template,
                            request_schema=self._request_schema(op),
                            response_schema=self._response_schema(op),
                            auth_strategy="unknown",
                            source="openapi",
                        )
                    )
                except ValidationError:
                    continue
        return OpenAPIIngestResult(
            endpoints=tuple(endpoints),
            title=self._info(spec, "title"),
            version=self._info(spec, "version"),
        )

    def cross_check(
        self,
        *,
        ingested: Iterable[ApiEndpoint],
        observed: Iterable[ApiEndpoint],
    ) -> OpenAPICrossCheck:
        ingested_paths = {ep.path for ep in ingested}
        observed_paths = {ep.path for ep in observed}
        undocumented = sorted(observed_paths - ingested_paths)
        expected = sorted(ingested_paths - observed_paths)
        return OpenAPICrossCheck(
            undocumented_paths=tuple(undocumented),
            expected_but_not_observed=tuple(expected),
        )

    def _load(
        self,
        *,
        path: Path | None,
        url: str | None,
        http: httpx.Client | None,
    ) -> dict[str, Any]:
        if path is not None:
            text = Path(path).read_text(encoding="utf-8")
        else:
            assert url is not None
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(f"OpenAPI URL must use http(s); got {parsed.scheme!r}")
            owns_client = http is None
            client = http or httpx.Client(timeout=10.0, follow_redirects=True)
            try:
                response = client.get(url)
                response.raise_for_status()
                text = response.text
            finally:
                if owns_client:
                    client.close()
        # YAML is a superset of JSON for our purposes — accept both.
        loaded: Any = json.loads(text) if text.lstrip().startswith("{") else yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError("OpenAPI document must be a mapping at the root")
        return loaded

    def _request_schema(self, op: dict[str, Any]) -> dict[str, Any] | None:
        body = op.get("requestBody")
        if not isinstance(body, dict):
            return None
        content = body.get("content")
        if not isinstance(content, dict):
            return None
        for media_type, media in content.items():
            if not isinstance(media, dict):
                continue
            schema = media.get("schema")
            if isinstance(schema, dict):
                return {"media_type": media_type, "schema": schema}
        return None

    def _response_schema(self, op: dict[str, Any]) -> dict[str, Any] | None:
        responses = op.get("responses")
        if not isinstance(responses, dict):
            return None
        # Prefer the 2xx response if any.
        ordered_keys = sorted(
            (k for k in responses if isinstance(k, str)),
            key=lambda k: (not k.startswith("2"), k),
        )
        for status_key in ordered_keys:
            entry = responses[status_key]
            if not isinstance(entry, dict):
                continue
            content = entry.get("content")
            if not isinstance(content, dict):
                continue
            for media_type, media in content.items():
                if not isinstance(media, dict):
                    continue
                schema = media.get("schema")
                if isinstance(schema, dict):
                    return {"status": status_key, "media_type": media_type, "schema": schema}
        return None

    def _info(self, spec: dict[str, Any], key: str) -> str | None:
        info = spec.get("info")
        if isinstance(info, dict):
            value = info.get(key)
            if isinstance(value, str):
                return value
        return None


__all__ = ["OpenAPICrossCheck", "OpenAPIIngestResult", "OpenAPIIngester"]
