"""GraphQL ingestion (task 05.06).

Reads either a local SDL file or runs an introspection query against a
GraphQL endpoint, and emits one :class:`ApiEndpoint` per top-level field
on the ``Query``, ``Mutation``, and ``Subscription`` types. All such
endpoints share the same HTTP path + POST method by convention but the
endpoint ``path`` field encodes the operation kind, e.g. ``/graphql#query.users``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
from graphql import build_schema, get_introspection_query, validate_schema
from pydantic import ValidationError

from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.ids import IdGenerator

_OPERATION_TYPES = ("query", "mutation", "subscription")


@dataclass(frozen=True)
class GraphQLIngestResult:
    endpoints: tuple[ApiEndpoint, ...] = field(default_factory=tuple)
    endpoint_url: str | None = None


class GraphQLIngester:
    def __init__(self, id_generator: IdGenerator | None = None) -> None:
        self._ids = id_generator or IdGenerator()

    def ingest_sdl(self, sdl_path: Path, *, endpoint_url: str = "/graphql") -> GraphQLIngestResult:
        sdl = Path(sdl_path).read_text(encoding="utf-8")
        schema = build_schema(sdl)
        errors = validate_schema(schema)
        if errors:
            raise ValueError(f"Invalid GraphQL schema: {errors[0].message}")
        return self._collect(schema, endpoint_url=endpoint_url)

    def ingest_introspection(
        self,
        endpoint_url: str,
        *,
        http: httpx.Client | None = None,
    ) -> GraphQLIngestResult:
        parsed = urlparse(endpoint_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"GraphQL URL must use http(s); got {parsed.scheme!r}")
        owns_client = http is None
        client = http or httpx.Client(timeout=10.0)
        try:
            response = client.post(
                endpoint_url,
                json={"query": get_introspection_query()},
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                client.close()
        introspection = data.get("data") if isinstance(data, dict) else None
        if not isinstance(introspection, dict):
            raise ValueError("Introspection response missing `data` field")
        from graphql import build_client_schema

        schema = build_client_schema(introspection)  # type: ignore[arg-type]
        return self._collect(schema, endpoint_url=endpoint_url)

    def _collect(self, schema: object, *, endpoint_url: str) -> GraphQLIngestResult:
        endpoints: list[ApiEndpoint] = []
        getter = getattr(schema, "type_map", {})
        type_map = getter if isinstance(getter, dict) else {}
        for op_kind in _OPERATION_TYPES:
            attr_name = f"{op_kind}_type"
            op_type = getattr(schema, attr_name, None)
            if op_type is None:
                continue
            fields = getattr(op_type, "fields", {}) or {}
            for field_name in fields:
                path = f"{endpoint_url}#{op_kind}.{field_name}"
                try:
                    endpoints.append(
                        ApiEndpoint(
                            id=self._ids.new("API"),
                            method="POST",
                            path=path,
                            auth_strategy="unknown",
                            source="graphql",
                        )
                    )
                except ValidationError:
                    continue
        # Silence "type_map unused" by referencing it (helps mypy).
        _ = type_map
        return GraphQLIngestResult(
            endpoints=tuple(endpoints),
            endpoint_url=endpoint_url,
        )


__all__ = ["GraphQLIngestResult", "GraphQLIngester"]
