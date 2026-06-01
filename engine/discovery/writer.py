"""Discovery artifact writer.

Persists the five discovery JSON artifacts plus a human-readable Markdown
summary into the run dir:

- ``discovery.json`` — full DiscoveryGraph + crawl meta
- ``forms.json`` — FormsInventory + observations
- ``api.json`` — endpoints + suspicions + cross-check
- ``auth.json`` — AuthBoundaryReport (env-var names only, no secrets)
- ``risk.json`` — RiskMap
- ``discovery.report.md`` — deterministic Markdown summary

All writes are byte-stable (sorted keys, fixed indent, deterministic float
format). Atomic write semantics (write → fsync → rename) live in
``engine.orchestrator.artifacts`` and are reused here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from engine.discovery.pipeline import DiscoveryResult
from engine.domain.schema import CONFIG_SCHEMA_VERSION


def _to_jsonable(value: Any) -> Any:
    """Convert dataclass / pydantic / set / Path / tuple → JSON-safe."""

    if value is None:
        return None
    if isinstance(value, str | int | bool | float):
        return value
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable(asdict(value))
    return str(value)


def _dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def write_discovery_artifacts(
    *,
    result: DiscoveryResult,
    out_dir: Path,
) -> dict[str, Path]:
    """Write all five JSON artifacts + the Markdown summary. Return the paths."""

    written: dict[str, Path] = {}

    discovery_payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "graph": _to_jsonable(result.graph),
        "crawl": {
            "pages": _to_jsonable(result.anonymous_crawl.pages),
            "robots_disallowed": list(result.anonymous_crawl.robots_disallowed),
            "skipped_external": list(result.anonymous_crawl.skipped_external),
        },
        "dom_observations": _to_jsonable(result.dom_map.observations),
        "unreachable_links": list(result.dom_map.unreachable_links),
        "repeated_components": [
            {"role": r, "accessible_name": n, "count": c}
            for (r, n, c) in result.dom_map.repeated_components
        ],
    }
    discovery_path = out_dir / "discovery.json"
    _dump(discovery_path, discovery_payload)
    written["discovery"] = discovery_path

    forms_payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "forms": _to_jsonable(result.forms),
        "observations": _to_jsonable(result.forms_inventory.observations),
        "recaptcha_routes": list(result.forms_inventory.recaptcha_routes),
    }
    forms_path = out_dir / "forms.json"
    _dump(forms_path, forms_payload)
    written["forms"] = forms_path

    api_payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "endpoints": _to_jsonable(result.api_endpoints),
        "referenced_only_paths": list(result.api_detector_result.referenced_only_paths),
        "observed_5xx_paths": list(result.api_detector_result.observed_5xx_paths),
        "suspicions": _to_jsonable(result.suspicions),
        "openapi": {
            "title": result.openapi_result.title,
            "version": result.openapi_result.version,
            "endpoint_count": len(result.openapi_result.endpoints),
            "undocumented_paths": list(result.openapi_cross_check.undocumented_paths),
            "expected_but_not_observed": list(result.openapi_cross_check.expected_but_not_observed),
        },
        "graphql": {
            "endpoint_url": result.graphql_result.endpoint_url,
            "operation_count": len(result.graphql_result.endpoints),
        },
    }
    api_path = out_dir / "api.json"
    _dump(api_path, api_payload)
    written["api"] = api_path

    auth_payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "login_succeeded": result.auth_report.login_succeeded,
        "login_url": result.auth_report.login_url,
        "username_env_name": result.auth_report.username_env_name,
        "password_env_name": result.auth_report.password_env_name,
        "verdicts": _to_jsonable(result.auth_report.verdicts),
        "boundaries": _to_jsonable(result.auth_report.boundaries),
    }
    auth_path = out_dir / "auth.json"
    _dump(auth_path, auth_payload)
    written["auth"] = auth_path

    risk_payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "risk_map": _to_jsonable(result.risk_map),
    }
    risk_path = out_dir / "risk.json"
    _dump(risk_path, risk_payload)
    written["risk"] = risk_path

    md_path = out_dir / "discovery.report.md"
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    written["markdown"] = md_path

    return written


def _render_markdown(result: DiscoveryResult) -> str:
    lines: list[str] = []
    lines.append("# Discovery report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Routes discovered: **{len(result.graph.routes)}**")
    lines.append(f"- Elements captured: **{len(result.graph.elements)}**")
    lines.append(f"- Forms inventoried: **{len(result.graph.forms)}**")
    lines.append(f"- API endpoints (observed + ingested): **{len(result.graph.api_endpoints)}**")
    lines.append(f"- Auth boundaries: **{len(result.graph.auth_boundaries)}**")
    lines.append("")
    lines.append(f"- Anonymous crawl pages: **{len(result.anonymous_crawl.pages)}**")
    lines.append(f"- robots.txt disallowed: **{len(result.anonymous_crawl.robots_disallowed)}**")
    lines.append(
        f"- External / off-host links skipped: **{len(result.anonymous_crawl.skipped_external)}**"
    )
    lines.append("")
    lines.append("## Risk map")
    lines.append("")
    if not result.risk_map.entries:
        lines.append("_No routes scored._")
    else:
        sorted_entries = sorted(result.risk_map.entries, key=lambda e: (-e.score, e.route_id))
        lines.append("| Route ID | Score | Top justifications |")
        lines.append("|---|---:|---|")
        for entry in sorted_entries[:25]:
            justifications = "; ".join(entry.justifications[:3]) or "_(none)_"
            lines.append(f"| `{entry.route_id}` | {entry.score:.2f} | {justifications} |")
    lines.append("")
    if result.openapi_result.endpoints:
        lines.append("## OpenAPI cross-check")
        lines.append("")
        lines.append(
            f"- Spec: **{result.openapi_result.title or 'untitled'}** "
            f"v{result.openapi_result.version or '?'} "
            f"({len(result.openapi_result.endpoints)} endpoints)"
        )
        if result.openapi_cross_check.undocumented_paths:
            lines.append("- Undocumented (observed but not in spec):")
            for path in result.openapi_cross_check.undocumented_paths:
                lines.append(f"  - `{path}`")
        if result.openapi_cross_check.expected_but_not_observed:
            lines.append("- Expected but never reached during the crawl:")
            for path in result.openapi_cross_check.expected_but_not_observed:
                lines.append(f"  - `{path}`")
        lines.append("")
    if result.suspicions:
        lines.append("## API suspicions")
        lines.append("")
        for sus in result.suspicions:
            lines.append(f"- `{sus.endpoint_path}` — **{sus.kind}**: {sus.detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["write_discovery_artifacts"]
