"""Frontend secrets / data-leakage check.

Two sub-scans:

1. **JS bundle scan** (HTTP-only). For each route in ``ctx.routes``,
 GET the page, extract every ``<script src=...>`` URL, fetch the JS
 bundle, and run :func:`scan_for_secrets` against the body.
2. **DOM / storage snapshot scan** (optional). Reads JSON files
 matching ``security/snapshots/<route-slug>.json`` under the run
 directory if any exist. The snapshot is produced by a separate
 Playwright-side helper (see ``packages/ts-runtime/src/security/
 capture_secrets.ts``); a Phase-26 example app will demonstrate
 wiring. When no snapshot file is present, this scan is silently
 skipped.

The scanner never persists the matched secret value — only a short
masked preview (``"AKIA…"``) and the category. CLAUDE §33 forbids
secrets-in-logs full stop.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from engine.policy.audit_log import write_audit_entry
from engine.policy.safety import SafetyPolicy

from modules.security.checks.context import CheckContext
from modules.security.models import SecurityCheckResult, SecurityIssue
from modules.security.rules import rule_by_id
from modules.security.secret_patterns import (
    PiiMatch,
    SecretMatch,
    scan_for_pii,
    scan_for_secrets,
)

CHECK_NAME = "frontend_secrets"

_SCRIPT_SRC_RE = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*['"](?P<src>[^'"]+)['"]""",
    re.IGNORECASE,
)

MAX_BUNDLE_BYTES = 4 * 1024 * 1024  # 4 MB safety cap per bundle


def _route_slug(route: str) -> str:
    if route in {"", "/"}:
        return "root"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", route).strip("-")
    return cleaned or "root"


def _bundle_urls(html: str, page_url: str) -> list[str]:
    out: list[str] = []
    for match in _SCRIPT_SRC_RE.finditer(html):
        src = match.group("src").strip()
        if not src:
            continue
        if src.startswith(("data:", "javascript:", "blob:")):
            continue
        out.append(urljoin(page_url, src))
    # Stable, de-duplicated
    seen: set[str] = set()
    ordered: list[str] = []
    for url in out:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _snapshot_path(snapshot_dir: Path | None, route: str) -> Path | None:
    if snapshot_dir is None:
        return None
    candidate = snapshot_dir / f"{_route_slug(route)}.json"
    return candidate if candidate.exists() else None


def _load_snapshot(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): v for k, v in payload.items()}


def run_frontend_secrets_check(
    ctx: CheckContext,
    *,
    snapshot_dir: Path | None = None,
) -> SecurityCheckResult:
    SafetyPolicy().enforce(ctx.target, ctx.safety.mode)
    start = time.monotonic()
    issues: list[SecurityIssue] = []
    targets_scanned = 0
    seen_evidence: set[tuple[str, str, str]] = set()
    """Dedup key: ``(rule_id, route, category)``."""

    for route in ctx.routes:
        absolute = urljoin(ctx.target_base_url, route)
        try:
            response = ctx.client.get(absolute)
        except httpx.HTTPError as exc:
            _audit(ctx, route=route, kind="error", detail=str(exc))
            continue
        targets_scanned += 1
        _audit(ctx, route=route, kind="probe", detail=f"status={response.status_code}")
        html = response.text or ""
        for bundle_url in _bundle_urls(html, absolute):
            issues.extend(
                _scan_bundle(
                    ctx=ctx,
                    bundle_url=bundle_url,
                    route=route,
                    seen=seen_evidence,
                )
            )

        snapshot_path = _snapshot_path(snapshot_dir, route)
        if snapshot_path is not None:
            issues.extend(
                _scan_snapshot(
                    ctx=ctx,
                    snapshot_path=snapshot_path,
                    route=route,
                    seen=seen_evidence,
                )
            )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return SecurityCheckResult(
        check=CHECK_NAME,
        targets_scanned=targets_scanned,
        issues=tuple(issues),
        duration_ms=elapsed_ms,
    )


def _scan_bundle(
    *,
    ctx: CheckContext,
    bundle_url: str,
    route: str,
    seen: set[tuple[str, str, str]],
) -> list[SecurityIssue]:
    parsed = urlparse(bundle_url)
    if parsed.scheme not in {"http", "https"}:
        return []
    try:
        response = ctx.client.get(bundle_url)
    except httpx.HTTPError as exc:
        _audit(ctx, route=route, kind="bundle_error", detail=str(exc))
        return []
    _audit(ctx, route=route, kind="bundle", detail=f"url=<bundle> status={response.status_code}")
    content = response.content[:MAX_BUNDLE_BYTES]
    text = content.decode("utf-8", errors="replace")
    matches = scan_for_secrets(text)
    out: list[SecurityIssue] = []
    for match in matches:
        dedup_key = ("SEC-FRONTEND-SECRET-IN-BUNDLE", route, match.category)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        out.append(_make_bundle_issue(match, route=route, bundle_url=bundle_url))
    return out


def _scan_snapshot(
    *,
    ctx: CheckContext,
    snapshot_path: Path,
    route: str,
    seen: set[tuple[str, str, str]],
) -> list[SecurityIssue]:
    snapshot = _load_snapshot(snapshot_path)
    if not snapshot:
        return []
    issues: list[SecurityIssue] = []

    dom_html = str(snapshot.get("dom_html", "") or "")
    local_storage = snapshot.get("local_storage", {}) or {}
    session_storage = snapshot.get("session_storage", {}) or {}
    is_authenticated = bool(snapshot.get("authenticated", False))

    # Storage token / API-key scan
    for source_name, source_map in (
        ("local_storage", local_storage),
        ("session_storage", session_storage),
    ):
        if not isinstance(source_map, dict):
            continue
        for key, value in source_map.items():
            payload = f"{key}={value}"
            for match in scan_for_secrets(payload):
                dedup_key = ("SEC-FRONTEND-TOKEN-IN-STORAGE", route, match.category)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                issues.append(
                    _make_storage_issue(
                        match=match,
                        route=route,
                        storage=source_name,
                        key=str(key),
                    )
                )

    # PII-in-DOM scan (only when snapshot is anonymous).
    if dom_html and not is_authenticated:
        for pii in scan_for_pii(dom_html):
            dedup_key = ("SEC-FRONTEND-PII-IN-DOM", route, pii.category)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            issues.append(_make_pii_issue(pii, route=route))
    return issues


# ---------------------------------------------------------------------
# Issue builders
# ---------------------------------------------------------------------


def _make_bundle_issue(
    match: SecretMatch,
    *,
    route: str,
    bundle_url: str,
) -> SecurityIssue:
    rule = rule_by_id("SEC-FRONTEND-SECRET-IN-BUNDLE")
    return SecurityIssue(
        rule_id=rule.rule_id,
        severity="high",
        confidence=0.85,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence={
            "bundle_url": bundle_url,
            "secret_category": match.category,
            "preview": match.preview,
            "offset": match.offset,
        },
        recommendation=rule.recommendation,
    )


def _make_storage_issue(
    *,
    match: SecretMatch,
    route: str,
    storage: str,
    key: str,
) -> SecurityIssue:
    rule = rule_by_id("SEC-FRONTEND-TOKEN-IN-STORAGE")
    return SecurityIssue(
        rule_id=rule.rule_id,
        severity="medium",
        confidence=0.9,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence={
            "storage": storage,
            "key": key,
            "secret_category": match.category,
            "preview": match.preview,
        },
        recommendation=rule.recommendation,
    )


def _make_pii_issue(match: PiiMatch, *, route: str) -> SecurityIssue:
    rule = rule_by_id("SEC-FRONTEND-PII-IN-DOM")
    return SecurityIssue(
        rule_id=rule.rule_id,
        severity="medium",
        confidence=0.6,
        title=rule.title,
        description=rule.description,
        route=route,
        evidence={
            "pii_category": match.category,
            "preview": match.preview,
            "offset": match.offset,
        },
        recommendation=rule.recommendation,
    )


def _audit(ctx: CheckContext, *, route: str, kind: str, detail: str) -> None:
    if ctx.audit_log_path is None:
        return
    write_audit_entry(
        ctx.audit_log_path,
        {
            "event": f"security.{CHECK_NAME}.{kind}",
            "run_id": ctx.run_id,
            "route": route,
            "detail": detail,
        },
    )


__all__ = [
    "CHECK_NAME",
    "MAX_BUNDLE_BYTES",
    "run_frontend_secrets_check",
]
