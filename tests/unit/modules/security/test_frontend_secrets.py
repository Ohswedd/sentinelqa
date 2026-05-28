"""Unit tests for the frontend-secrets check (Phase 13.08)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from modules.security.checks.frontend_secrets import run_frontend_secrets_check


def test_no_findings_for_clean_page(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body>safe</body></html>")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx)
    assert result.issues == ()
    assert result.targets_scanned == 1


def test_detects_aws_key_in_js_bundle(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(
                200,
                html="""<html><body><script src="/app.js"></script></body></html>""",
            )
        if request.url.path == "/app.js":
            return httpx.Response(
                200,
                text="const cfg = { ak: 'AKIAIOSFODNN7EXAMPLE' };",
                headers={"content-type": "application/javascript"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx)
    assert any(i.rule_id == "SEC-FRONTEND-SECRET-IN-BUNDLE" for i in result.issues)


def test_dedup_within_route(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(
                200,
                html=(
                    "<html><body>"
                    """<script src="/a.js"></script>"""
                    """<script src="/b.js"></script>"""
                    "</body></html>"
                ),
            )
        return httpx.Response(
            200,
            text="const ak = 'AKIAIOSFODNN7EXAMPLE';",
            headers={"content-type": "application/javascript"},
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx)
    bundle_issues = [i for i in result.issues if i.rule_id == "SEC-FRONTEND-SECRET-IN-BUNDLE"]
    assert len(bundle_issues) == 1


def test_snapshot_detects_token_in_local_storage(tmp_path: Path, make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html></html>")

    transport = httpx.MockTransport(handler)
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    payload = {
        "dom_html": "<html></html>",
        "local_storage": {"id_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.signature_part_abc"},
        "session_storage": {},
        "authenticated": True,
    }
    (snapshot_dir / "root.json").write_text(json.dumps(payload), encoding="utf-8")
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx, snapshot_dir=snapshot_dir)
    assert any(i.rule_id == "SEC-FRONTEND-TOKEN-IN-STORAGE" for i in result.issues)


def test_snapshot_pii_only_anonymous(tmp_path: Path, make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html></html>")

    transport = httpx.MockTransport(handler)
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    payload_auth = {
        "dom_html": "Contact: bob@example.com",
        "authenticated": True,
    }
    payload_anon = {
        "dom_html": "Contact: bob@example.com",
        "authenticated": False,
    }
    (snapshot_dir / "root.json").write_text(json.dumps(payload_auth), encoding="utf-8")
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx, snapshot_dir=snapshot_dir)
    assert all(i.rule_id != "SEC-FRONTEND-PII-IN-DOM" for i in result.issues)
    # Switch snapshot to anon
    (snapshot_dir / "root.json").write_text(json.dumps(payload_anon), encoding="utf-8")
    result2 = run_frontend_secrets_check(ctx, snapshot_dir=snapshot_dir)
    assert any(i.rule_id == "SEC-FRONTEND-PII-IN-DOM" for i in result2.issues)
