"""Production wiring that materialises :class:`LlmAuditInputs`.

The module deliberately reuses signals captured by earlier phases. The
loader walks a few well-known paths under ``<signals_root>`` and the
discovery output:

* ``discovery.json`` — link references + observed routes
* ``api.json`` — observed + OpenAPI endpoints
* ``forms.json`` — forms inventory
* ``llm_audit/signals.json`` — optional structured signal bundle for
 the checks that need runtime evidence (storage dumps, console
 entries, loading/error probes, validation probes, button activity).
 Tests construct this file directly; later phases (healer,
 chaos) can extend the writer.
* ``llm_audit/source_files.json`` — optional source-file bodies for the
 hardcoded-credential scanner. Production wiring builds this from
 ``config.source.root`` when present.

Missing files yield empty tuples — the corresponding checks see no
input and emit no findings (CLAUDE §37: no fake completion).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from modules.llm_audit.models import (
    ApiReference,
    AuthRouteProbe,
    BrowserStorageSample,
    BundleSnippet,
    ButtonObservation,
    ConsoleEntry,
    FormSignal,
    LinkReference,
    LlmAuditInputs,
    LoadingErrorObservation,
    RenderedTextSample,
    ResourceCrudSignal,
    SourceFile,
    ValidationProbe,
)


def load_inputs(
    *,
    discovery_path: Path | None,
    signals_root: Path | None,
    third_party_console_hosts: tuple[str, ...] = (),
) -> LlmAuditInputs:
    """Materialise :class:`LlmAuditInputs` from disk."""

    discovery_payload = _read_json(discovery_path)
    api_payload = _read_json(_sibling(discovery_path, "api.json"))
    forms_payload = _read_json(_sibling(discovery_path, "forms.json"))
    signals_payload = _read_json(_signal_file(signals_root, "signals.json"))
    source_files_payload = _read_json(_signal_file(signals_root, "source_files.json"))

    link_refs = _link_references(discovery_payload)
    observed_routes, observed_status = _observed_routes(discovery_payload)
    api_refs = _api_references(api_payload)
    observed_endpoints, openapi_endpoints = _api_endpoints(api_payload)
    forms = _forms(forms_payload, signals_payload)
    bundles = _bundles(signals_payload)
    rendered_text = _rendered_text(signals_payload)
    resources = _resources(signals_payload)
    auth_probes = _auth_route_probes(signals_payload)
    buttons = _buttons(signals_payload)
    storage = _storage_samples(signals_payload)
    loading_error = _loading_error_obs(signals_payload)
    validation = _validation_probes(signals_payload)
    console = _console_entries(signals_payload)
    source_files = _source_files(source_files_payload)

    return LlmAuditInputs(
        buttons=buttons,
        link_references=link_refs,
        api_references=api_refs,
        observed_routes=observed_routes,
        observed_route_status=observed_status,
        observed_endpoints=observed_endpoints,
        openapi_endpoints=openapi_endpoints,
        bundles=bundles,
        rendered_text=rendered_text,
        forms=forms,
        resources=resources,
        auth_route_probes=auth_probes,
        source_files=source_files,
        storage_samples=storage,
        loading_error_observations=loading_error,
        validation_probes=validation,
        console_entries=console,
        third_party_console_hosts=third_party_console_hosts,
        discovery_path=discovery_path,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path | None) -> Mapping[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(loaded, Mapping):
        return loaded
    return {}


def _sibling(discovery_path: Path | None, name: str) -> Path | None:
    if discovery_path is None:
        return None
    return discovery_path.parent / name


def _signal_file(root: Path | None, name: str) -> Path | None:
    if root is None:
        return None
    return root / name


def _link_references(discovery: Mapping[str, Any]) -> tuple[LinkReference, ...]:
    pages = (
        discovery.get("crawl", {}).get("pages", [])
        if isinstance(discovery.get("crawl"), Mapping)
        else []
    )
    out: list[LinkReference] = []
    if not isinstance(pages, list):
        return ()
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        source = str(page.get("url") or "")
        if not source:
            continue
        links = page.get("discovered_links") or ()
        if not isinstance(links, list):
            continue
        for link in links:
            if not isinstance(link, str):
                continue
            out.append(
                LinkReference(
                    source_route=source,
                    target_path=link,
                    source="anchor",
                ),
            )
    return tuple(out)


def _observed_routes(
    discovery: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, int]]:
    pages = (
        discovery.get("crawl", {}).get("pages", [])
        if isinstance(discovery.get("crawl"), Mapping)
        else []
    )
    routes: list[str] = []
    status: dict[str, int] = {}
    if not isinstance(pages, list):
        return (), {}
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        url = str(page.get("url") or "")
        if not url:
            continue
        routes.append(url)
        raw_status = page.get("status_code")
        if isinstance(raw_status, int):
            status[url] = raw_status
    return tuple(routes), status


def _api_references(api_payload: Mapping[str, Any]) -> tuple[ApiReference, ...]:
    referenced_only = api_payload.get("referenced_only_paths", []) or []
    out: list[ApiReference] = []
    if isinstance(referenced_only, list):
        for path in referenced_only:
            if isinstance(path, str) and path:
                out.append(ApiReference(path=path, method="GET"))
    return tuple(out)


def _api_endpoints(
    api_payload: Mapping[str, Any],
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    observed: list[tuple[str, str]] = []
    documented: list[tuple[str, str]] = []
    endpoints = api_payload.get("endpoints", []) or []
    if isinstance(endpoints, list):
        for ep in endpoints:
            if not isinstance(ep, Mapping):
                continue
            method = str(ep.get("method") or "GET")
            path = str(ep.get("path") or "")
            if path:
                observed.append((method, path))
    openapi = api_payload.get("openapi", {})
    if isinstance(openapi, Mapping):
        # writer only includes summary counts; production
        # wiring re-walks `discovery.openapi_ingest_result` if needed.
        endpoint_paths = openapi.get("expected_but_not_observed", []) or []
        if isinstance(endpoint_paths, list):
            for path in endpoint_paths:
                if isinstance(path, str) and path:
                    documented.append(("GET", path))
    return tuple(observed), tuple(documented)


def _forms(
    forms_payload: Mapping[str, Any],
    signals_payload: Mapping[str, Any],
) -> tuple[FormSignal, ...]:
    forms = forms_payload.get("forms", []) or []
    exercises = signals_payload.get("form_exercises", {}) if signals_payload else {}
    if not isinstance(exercises, Mapping):
        exercises = {}
    out: list[FormSignal] = []
    if not isinstance(forms, list):
        return ()
    for form in forms:
        if not isinstance(form, Mapping):
            continue
        form_id = str(form.get("id") or form.get("form_id") or "")
        if not form_id:
            continue
        action_url = form.get("action_url")
        exercise = exercises.get(form_id) if isinstance(exercises, Mapping) else None
        was_exercised = bool(exercise and exercise.get("exercised"))
        produced_network: bool | None = None
        if isinstance(exercise, Mapping) and "produced_network_request" in exercise:
            produced_network = bool(exercise["produced_network_request"])
        out.append(
            FormSignal(
                form_id=form_id,
                route_url=str(form.get("route_url") or action_url or ""),
                action_url=str(action_url) if isinstance(action_url, str) else None,
                method=str(form.get("method") or "POST"),
                submit_handler_present=bool(form.get("submit_handler_present", True)),
                was_exercised=was_exercised,
                produced_network_request=produced_network,
            ),
        )
    return tuple(out)


def _bundles(signals: Mapping[str, Any]) -> tuple[BundleSnippet, ...]:
    raw = signals.get("bundles", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[BundleSnippet] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            path = str(entry.get("path") or "")
            body = str(entry.get("body") or "")
            if path and body:
                out.append(BundleSnippet(path=path, body=body))
    return tuple(out)


def _rendered_text(signals: Mapping[str, Any]) -> tuple[RenderedTextSample, ...]:
    raw = signals.get("rendered_text", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[RenderedTextSample] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            text = str(entry.get("text") or "")
            route = str(entry.get("route_url") or "")
            if not text or not route:
                continue
            out.append(
                RenderedTextSample(
                    route_url=route,
                    text=text,
                    is_authenticated_flow=bool(entry.get("is_authenticated_flow", False)),
                    priority=str(entry.get("priority") or "p3"),
                    selector=(str(entry["selector"]) if entry.get("selector") else None),
                ),
            )
    return tuple(out)


def _resources(signals: Mapping[str, Any]) -> tuple[ResourceCrudSignal, ...]:
    raw = signals.get("resources", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[ResourceCrudSignal] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            name = str(entry.get("resource") or "")
            if not name:
                continue
            out.append(
                ResourceCrudSignal(
                    resource=name,
                    has_create=bool(entry.get("has_create", False)),
                    has_read=bool(entry.get("has_read", False)),
                    has_update=bool(entry.get("has_update", False)),
                    has_delete=bool(entry.get("has_delete", False)),
                    ui_has_create_button=bool(entry.get("ui_has_create_button", False)),
                    ui_has_edit_button=bool(entry.get("ui_has_edit_button", False)),
                    ui_has_delete_button=bool(entry.get("ui_has_delete_button", False)),
                    sample_endpoint=(
                        str(entry["sample_endpoint"]) if entry.get("sample_endpoint") else None
                    ),
                ),
            )
    return tuple(out)


def _auth_route_probes(signals: Mapping[str, Any]) -> tuple[AuthRouteProbe, ...]:
    raw = signals.get("auth_route_probes", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[AuthRouteProbe] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            path = str(entry.get("route_path") or "")
            if not path:
                continue
            status_raw = entry.get("backend_status_code")
            status = int(status_raw) if isinstance(status_raw, int) else None
            out.append(
                AuthRouteProbe(
                    route_path=path,
                    method=str(entry.get("method") or "GET"),
                    role=str(entry.get("role") or "anonymous"),
                    ui_visible=bool(entry.get("ui_visible", False)),
                    backend_status_code=status,
                ),
            )
    return tuple(out)


def _buttons(signals: Mapping[str, Any]) -> tuple[ButtonObservation, ...]:
    raw = signals.get("buttons", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[ButtonObservation] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            label = str(entry.get("label") or "")
            selector = str(entry.get("selector") or "")
            route = str(entry.get("route_url") or "")
            if not (label and selector and route):
                continue
            out.append(
                ButtonObservation(
                    route_url=route,
                    selector=selector,
                    label=label,
                    disabled=bool(entry.get("disabled", False)),
                    has_static_handler=bool(entry.get("has_static_handler", False)),
                    observed_network_within_2s=_optional_bool(
                        entry.get("observed_network_within_2s")
                    ),
                    observed_navigation=_optional_bool(entry.get("observed_navigation")),
                    observed_console_error=_optional_bool(entry.get("observed_console_error")),
                    observed_dom_change=_optional_bool(entry.get("observed_dom_change")),
                    is_decorative=bool(entry.get("is_decorative", False)),
                    is_disclosure=bool(entry.get("is_disclosure", False)),
                ),
            )
    return tuple(out)


def _storage_samples(signals: Mapping[str, Any]) -> tuple[BrowserStorageSample, ...]:
    raw = signals.get("storage_samples", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[BrowserStorageSample] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            entries = entry.get("entries") or {}
            if not isinstance(entries, Mapping):
                continue
            out.append(
                BrowserStorageSample(
                    route_url=str(entry.get("route_url") or ""),
                    store=str(entry.get("store") or "localStorage"),
                    entries={str(k): str(v) for k, v in entries.items()},
                ),
            )
    return tuple(out)


def _loading_error_obs(
    signals: Mapping[str, Any],
) -> tuple[LoadingErrorObservation, ...]:
    raw = signals.get("loading_error_observations", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[LoadingErrorObservation] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            forced = entry.get("forced_status")
            out.append(
                LoadingErrorObservation(
                    route_url=str(entry.get("route_url") or ""),
                    probed_endpoint=str(entry.get("probed_endpoint") or ""),
                    delay_ms=int(entry.get("delay_ms") or 0),
                    forced_status=int(forced) if isinstance(forced, int) else None,
                    showed_loading_indicator=bool(entry.get("showed_loading_indicator", False)),
                    showed_error_state=bool(entry.get("showed_error_state", False)),
                    ui_reported_success=bool(entry.get("ui_reported_success", False)),
                ),
            )
    return tuple(out)


def _validation_probes(signals: Mapping[str, Any]) -> tuple[ValidationProbe, ...]:
    raw = signals.get("validation_probes", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[ValidationProbe] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            out.append(
                ValidationProbe(
                    form_id=str(entry.get("form_id") or ""),
                    route_url=str(entry.get("route_url") or ""),
                    endpoint_path=str(entry.get("endpoint_path") or ""),
                    field=str(entry.get("field") or ""),
                    payload_kind=str(entry.get("payload_kind") or "missing"),
                    frontend_would_submit=bool(entry.get("frontend_would_submit", False)),
                    backend_status_code=int(entry.get("backend_status_code") or 0),
                ),
            )
    return tuple(out)


def _console_entries(signals: Mapping[str, Any]) -> tuple[ConsoleEntry, ...]:
    raw = signals.get("console_entries", []) if signals else []
    if not isinstance(raw, list):
        return ()
    out: list[ConsoleEntry] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            out.append(
                ConsoleEntry(
                    route_url=str(entry.get("route_url") or ""),
                    level=str(entry.get("level") or "log"),
                    text=str(entry.get("text") or ""),
                    source_url=(str(entry["source_url"]) if entry.get("source_url") else None),
                    is_unhandled_rejection=bool(entry.get("is_unhandled_rejection", False)),
                    ui_reported_success=bool(entry.get("ui_reported_success", False)),
                ),
            )
    return tuple(out)


def _source_files(payload: Mapping[str, Any]) -> tuple[SourceFile, ...]:
    raw = payload.get("source_files", []) if payload else []
    if not isinstance(raw, list):
        return ()
    out: list[SourceFile] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            path = str(entry.get("path") or "")
            body = str(entry.get("body") or "")
            if path and body:
                out.append(SourceFile(path=path, body=body))
    return tuple(out)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


__all__ = ["load_inputs"]
