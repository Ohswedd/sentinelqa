"""OpenAPI 3.x loader + endpoint extraction (Phase 22.02).

The loader accepts JSON or YAML. We use :mod:`openapi_spec_validator`
to refuse malformed specs at load time so every later check (contract,
negative, pagination, backward-compat) operates on a validated doc.

Per-operation schema validation uses :mod:`jsonschema` against the
``responses[<status>].content[<media>].schema`` block. OpenAPI's Schema
Object is a near-superset of JSON Schema; for MVP we treat unsupported
keywords as advisory rather than failing the check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator import validate as validate_openapi_spec

from modules.api.models import ApiSchemaEndpoint

_HTTP_METHODS: tuple[str, ...] = (
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
)


@dataclass(frozen=True)
class OpenApiOperation:
    """Subset of an OpenAPI operation that drives a single check."""

    method: str
    path: str
    operation_id: str | None
    request_body_required: bool
    request_body_schema: dict[str, Any] | None
    request_body_content_type: str | None
    response_schemas: dict[int, dict[str, Any]]
    response_content_type: dict[int, str]
    security_required: bool
    parameters: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class OpenApiDocument:
    """Parsed + validated OpenAPI document with derived view helpers."""

    spec: dict[str, Any]
    operations: tuple[OpenApiOperation, ...]
    base_paths: tuple[str, ...]

    def authenticated_operations(self) -> tuple[OpenApiOperation, ...]:
        return tuple(op for op in self.operations if op.security_required)

    def snapshot_endpoints(self) -> tuple[ApiSchemaEndpoint, ...]:
        out: list[ApiSchemaEndpoint] = []
        for op in self.operations:
            required_req: tuple[str, ...] = ()
            if op.request_body_schema is not None:
                required_req = _required_field_names(op.request_body_schema)
            statuses = tuple(sorted(op.response_schemas.keys()))
            required_res: list[str] = []
            field_types: list[tuple[str, str]] = []
            for status in statuses:
                schema = op.response_schemas[status]
                required_res.extend(f"{status}:{f}" for f in _required_field_names(schema))
                for field_name, field_type in _field_types(schema):
                    field_types.append((f"{status}:{field_name}", field_type))
            out.append(
                ApiSchemaEndpoint(
                    method=op.method.upper(),
                    path=op.path,
                    required_request_fields=required_req,
                    response_status_codes=statuses,
                    required_response_fields=tuple(required_res),
                    response_field_types=tuple(field_types),
                )
            )
        out.sort(key=lambda e: (e.method, e.path))
        return tuple(out)


def load_openapi(path: Path) -> OpenApiDocument:
    """Load + validate an OpenAPI spec from ``path``.

    Raises :class:`ValueError` if the file cannot be parsed or fails
    OpenAPI 3.x validation; callers in :class:`ApiModule` translate this
    into a ``skipped`` check rather than a crashed run.
    """

    raw = path.read_text(encoding="utf-8")
    spec_obj = yaml.safe_load(raw) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    if not isinstance(spec_obj, dict):
        raise ValueError(f"OpenAPI doc at {path} did not parse to a JSON object.")
    validate_openapi_spec(spec_obj)  # raises OpenAPIValidationError on bad spec
    operations = tuple(_extract_operations(spec_obj))
    servers = spec_obj.get("servers") or []
    base_paths: list[str] = []
    if isinstance(servers, list):
        for entry in servers:
            if isinstance(entry, dict):
                url = entry.get("url")
                if isinstance(url, str) and url:
                    base_paths.append(url)
    return OpenApiDocument(
        spec=spec_obj,
        operations=operations,
        base_paths=tuple(base_paths),
    )


def _extract_operations(spec: dict[str, Any]) -> list[OpenApiOperation]:
    out: list[OpenApiOperation] = []
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict):
        return out
    has_global_security = bool(spec.get("security"))
    for path_template, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            request_body = op.get("requestBody") or {}
            req_required = (
                bool(request_body.get("required", False))
                if isinstance(request_body, dict)
                else False
            )
            req_schema: dict[str, Any] | None = None
            req_content_type: str | None = None
            if isinstance(request_body, dict):
                content = request_body.get("content") or {}
                if isinstance(content, dict):
                    for media, media_obj in content.items():
                        if not isinstance(media_obj, dict):
                            continue
                        schema = media_obj.get("schema")
                        if isinstance(schema, dict):
                            req_schema = _resolve_refs(schema, spec)
                            req_content_type = media
                            break
            response_schemas: dict[int, dict[str, Any]] = {}
            response_content_types: dict[int, str] = {}
            responses = op.get("responses") or {}
            if isinstance(responses, dict):
                for status_key, response_obj in responses.items():
                    if not isinstance(response_obj, dict):
                        continue
                    if status_key == "default":
                        status_int = 0
                    else:
                        try:
                            status_int = int(status_key)
                        except (TypeError, ValueError):
                            continue
                    content = response_obj.get("content") or {}
                    if not isinstance(content, dict):
                        continue
                    for media, media_obj in content.items():
                        if not isinstance(media_obj, dict):
                            continue
                        schema = media_obj.get("schema")
                        if isinstance(schema, dict):
                            response_schemas[status_int] = _resolve_refs(schema, spec)
                            response_content_types[status_int] = media
                            break
            op_security = op.get("security")
            sec_required = bool(op_security) if op_security is not None else has_global_security
            parameters_raw = op.get("parameters") or []
            parameters: list[dict[str, Any]] = []
            if isinstance(parameters_raw, list):
                for p in parameters_raw:
                    if isinstance(p, dict):
                        parameters.append(_resolve_refs(p, spec))
            out.append(
                OpenApiOperation(
                    method=method,
                    path=path_template,
                    operation_id=op.get("operationId"),
                    request_body_required=req_required,
                    request_body_schema=req_schema,
                    request_body_content_type=req_content_type,
                    response_schemas=response_schemas,
                    response_content_type=response_content_types,
                    security_required=sec_required,
                    parameters=tuple(parameters),
                )
            )
    out.sort(key=lambda o: (o.path, o.method))
    return out


def _resolve_refs(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """One-level ``$ref`` resolver (sufficient for MVP schemas).

    OpenAPI specs that nest refs through many indirections are still
    parsed, but only the first hop is resolved; jsonschema validation
    later treats remaining refs as advisory. This avoids dragging in a
    full resolver dependency for MVP.
    """

    if "$ref" not in schema:
        return schema
    ref = schema["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    target: Any = spec
    for part in ref[2:].split("/"):
        if isinstance(target, dict) and part in target:
            target = target[part]
        else:
            return schema
    if isinstance(target, dict):
        return _resolve_refs(target, spec)
    return schema


def _required_field_names(schema: dict[str, Any]) -> tuple[str, ...]:
    required = schema.get("required") or ()
    if isinstance(required, list):
        return tuple(str(name) for name in required if isinstance(name, str))
    return ()


def _field_types(schema: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    props = schema.get("properties") or {}
    if isinstance(props, dict):
        for name, sub_schema in sorted(props.items()):
            if isinstance(sub_schema, dict):
                t = sub_schema.get("type")
                if isinstance(t, str):
                    out.append((str(name), t))
                elif isinstance(t, list) and t:
                    out.append((str(name), str(t[0])))
    return out


__all__ = [
    "OpenApiDocument",
    "OpenApiOperation",
    "load_openapi",
]
