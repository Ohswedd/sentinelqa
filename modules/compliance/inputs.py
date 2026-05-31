"""Load compliance signals from disk (Phase 34 / ADR-0046).

The compliance module reads optional signal files written by the
discovery / runner phases (or by tests). Missing files yield empty
tuples — the corresponding check simply sees no input and reports
``skipped`` (CLAUDE §37: no fake completion).

Expected layout under ``<signals_root>``:

- ``gdpr.json``  — list of :class:`GdprPageSignals`.
- ``ccpa.json``  — list of :class:`CcpaPageSignal`.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.compliance.models import (
    CcpaPageSignal,
    GdprBannerSignal,
    GdprCookie,
    GdprPageSignals,
)


def load_gdpr_signals(path: Path | None) -> tuple[GdprPageSignals, ...]:
    if path is None or not path.exists():
        return ()
    payload = _read_json(path)
    if not isinstance(payload, list):
        return ()
    out: list[GdprPageSignals] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        route = entry.get("route")
        if not isinstance(route, str):
            continue
        banner_payload = entry.get("banner") or {}
        if not isinstance(banner_payload, dict):
            banner_payload = {}
        banner = GdprBannerSignal(
            present=bool(banner_payload.get("present", False)),
            accept_one_click=bool(banner_payload.get("accept_one_click", True)),
            reject_one_click=bool(banner_payload.get("reject_one_click", True)),
            selector=str(banner_payload.get("selector", ""))[:2048],
        )
        cookies_raw = entry.get("cookies_on_first_load") or []
        cookies: list[GdprCookie] = []
        if isinstance(cookies_raw, list):
            for cookie in cookies_raw:
                if not isinstance(cookie, dict):
                    continue
                name = cookie.get("name")
                if not isinstance(name, str) or not name:
                    continue
                cookies.append(
                    GdprCookie(
                        name=name,
                        domain=str(cookie.get("domain", ""))[:256],
                        essential=bool(cookie.get("essential", False)),
                    )
                )
        out.append(
            GdprPageSignals(
                route=route,
                banner=banner,
                cookies_on_first_load=tuple(cookies),
            )
        )
    return tuple(out)


def load_ccpa_signals(path: Path | None) -> tuple[CcpaPageSignal, ...]:
    if path is None or not path.exists():
        return ()
    payload = _read_json(path)
    if not isinstance(payload, list):
        return ()
    out: list[CcpaPageSignal] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        route = entry.get("route")
        if not isinstance(route, str):
            continue
        out.append(
            CcpaPageSignal(
                route=route,
                link_text=str(entry.get("link_text", ""))[:256],
                link_href=str(entry.get("link_href", ""))[:2048],
                link_followed=bool(entry.get("link_followed", False)),
                target_has_opt_out_form=bool(entry.get("target_has_opt_out_form", False)),
            )
        )
    return tuple(out)


def _read_json(path: Path) -> object | None:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload


__all__ = ["load_ccpa_signals", "load_gdpr_signals"]
