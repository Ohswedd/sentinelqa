"""GraphQL SDL loader + operation extraction (Phase 22.03).

Uses :mod:`graphql` (graphql-core) to parse the SDL, build the schema,
and enumerate top-level query / mutation fields. For each field we
generate a minimal probe query (selecting every scalar return field
and the first scalar field of object types) and validate the server
response shape:

- Non-nullable return fields that come back ``null`` → high severity.
- Missing top-level fields → high.
- Type mismatch (object where scalar declared) → high.

Subscriptions are intentionally NOT probed — the MVP skips them with
an info-level note rather than holding open a websocket against an
unknown server (the documentation lists subscriptions as planned; full
support arrives with the chaos module's session work).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphql import (
    GraphQLField,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    Undefined,
    build_schema,
)

from modules.api.models import ApiSchemaEndpoint


@dataclass(frozen=True)
class GraphqlOperation:
    """One probeable GraphQL operation (query or mutation)."""

    kind: str  # "query" | "mutation"
    field_name: str
    return_type: str
    return_non_null: bool
    selection: str
    required_fields: tuple[str, ...]
    field_types: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GraphqlSchema:
    """Parsed GraphQL schema + derived operations."""

    schema: GraphQLSchema
    operations: tuple[GraphqlOperation, ...]
    raw_sdl: str

    def snapshot_endpoints(self) -> tuple[ApiSchemaEndpoint, ...]:
        out: list[ApiSchemaEndpoint] = []
        for op in self.operations:
            path = f"/{op.kind}/{op.field_name}"
            method = "POST"
            out.append(
                ApiSchemaEndpoint(
                    method=method,
                    path=path,
                    required_request_fields=(),
                    response_status_codes=(200,),
                    required_response_fields=op.required_fields,
                    response_field_types=op.field_types,
                )
            )
        out.sort(key=lambda e: (e.method, e.path))
        return tuple(out)


def load_graphql(path: Path) -> GraphqlSchema:
    """Load + parse a GraphQL SDL file."""

    raw = path.read_text(encoding="utf-8")
    schema = build_schema(raw)
    ops: list[GraphqlOperation] = []
    if schema.query_type is not None:
        ops.extend(_extract_ops(schema.query_type, "query"))
    if schema.mutation_type is not None:
        ops.extend(_extract_ops(schema.mutation_type, "mutation"))
    return GraphqlSchema(schema=schema, operations=tuple(ops), raw_sdl=raw)


def _extract_ops(obj_type: GraphQLObjectType, kind: str) -> list[GraphqlOperation]:
    out: list[GraphqlOperation] = []
    for field_name, field in obj_type.fields.items():
        if _has_required_arguments(field):
            # Skip ops that need non-default arguments — the MVP only
            # probes safe, argument-less fields so we never fabricate
            # a payload to a server.
            continue
        return_type = field.type
        non_null = isinstance(return_type, GraphQLNonNull)
        inner = return_type.of_type if isinstance(return_type, GraphQLNonNull) else return_type
        selection = _build_selection(inner)
        required = _required_response_paths(inner)
        types = _response_field_types(inner)
        out.append(
            GraphqlOperation(
                kind=kind,
                field_name=field_name,
                return_type=str(inner),
                return_non_null=non_null,
                selection=selection,
                required_fields=tuple(required),
                field_types=tuple(types),
            )
        )
    return out


def _has_required_arguments(field: GraphQLField) -> bool:
    for arg in field.args.values():
        # graphql-core uses the `Undefined` sentinel (not Python None) when
        # an argument was declared without a default. Treat absent or
        # explicit-Undefined as "no default" so we never probe a field
        # that requires the caller to supply a value.
        no_default = arg.default_value is Undefined or arg.default_value is None
        if isinstance(arg.type, GraphQLNonNull) and no_default:
            return True
    return False


def _build_selection(graphql_type: Any) -> str:
    """Build a minimal selection set for ``graphql_type``.

    For scalars: empty (scalars are leaf nodes selected by name only).
    For objects: select every scalar field. Lists / non-nulls unwrap.
    """

    if isinstance(graphql_type, GraphQLNonNull):
        return _build_selection(graphql_type.of_type)
    if isinstance(graphql_type, GraphQLList):
        return _build_selection(graphql_type.of_type)
    if isinstance(graphql_type, GraphQLObjectType):
        scalar_names: list[str] = []
        for sub_name, sub_field in graphql_type.fields.items():
            sub_type = sub_field.type
            inner = sub_type.of_type if isinstance(sub_type, GraphQLNonNull) else sub_type
            if isinstance(inner, GraphQLScalarType):
                scalar_names.append(sub_name)
        if not scalar_names:
            return ""
        return " { " + " ".join(scalar_names) + " }"
    return ""


def _required_response_paths(graphql_type: Any) -> list[str]:
    out: list[str] = []
    inner = graphql_type.of_type if isinstance(graphql_type, GraphQLNonNull) else graphql_type
    if isinstance(inner, GraphQLObjectType):
        for sub_name, sub_field in inner.fields.items():
            if isinstance(sub_field.type, GraphQLNonNull):
                out.append(sub_name)
    return out


def _response_field_types(graphql_type: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    inner = graphql_type.of_type if isinstance(graphql_type, GraphQLNonNull) else graphql_type
    if isinstance(inner, GraphQLObjectType):
        for sub_name, sub_field in sorted(inner.fields.items()):
            sub_type = sub_field.type
            sub_inner = sub_type.of_type if isinstance(sub_type, GraphQLNonNull) else sub_type
            out.append((sub_name, str(sub_inner)))
    return out


__all__ = ["GraphqlOperation", "GraphqlSchema", "load_graphql"]
