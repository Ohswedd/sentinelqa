"""Extra coverage tests for individual checks (Phase 13.13)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import yaml
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.context import CheckContext
from modules.security.checks.cookies import parse_set_cookie, run_cookies_check
from modules.security.checks.cors import run_cors_check
from modules.security.checks.csrf import run_csrf_check
from modules.security.checks.frontend_secrets import (
    _bundle_urls,
    _load_snapshot,
    _route_slug,
    _snapshot_path,
    run_frontend_secrets_check,
)
from modules.security.checks.headers import run_headers_check
from modules.security.checks.idor import (
    _candidate_segments,
    _replace_segment,
    _second_user_token,
    run_idor_check,
)
from modules.security.checks.sqli import _inject_into_query, run_sqli_check
from modules.security.checks.xss_reflected import _has_reflection, run_xss_reflected_check
from modules.security.checks.xss_stored import run_xss_stored_check
from modules.security.http_client import TokenBucket
from modules.security.secret_patterns import scan_for_pii, scan_for_secrets


def test_token_bucket_rate_limits_simply() -> None:
    bucket = TokenBucket(rate_per_second=1000.0)
    for _ in range(3):
        bucket.take()


def test_headers_audit_logs_with_no_audit_path(make_ctx, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={})

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",), audit_log_path=None)
    # audit_log_path=None means audit calls are no-ops.
    result = run_headers_check(ctx)
    assert result.targets_scanned == 1


def test_cookies_error_path(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_cookies_check(ctx)
    assert result.targets_scanned == 0


def test_cors_error_path(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/api",))
    result = run_cors_check(ctx)
    assert result.targets_scanned == 0


def test_csrf_error_path(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_csrf_check(ctx)
    assert result.targets_scanned == 0


def test_xss_reflected_error_path(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/search?q=hi",))
    result = run_xss_reflected_check(ctx)
    assert result.targets_scanned == 0


def test_xss_stored_with_invalid_proof_path(tmp_path: Path) -> None:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: http://localhost:8088\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
        f"  proof_of_authorization: {tmp_path / 'absent.yaml'}\n"
        "security:\n"
        "  mode: authorized_destructive\n"
        "  checks:\n"
        "    xss_stored: true\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="authorized_destructive",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(base_url="http://localhost:8088", timeout=1.0)
    try:
        ctx = CheckContext(
            run_id="RUN-AAAAAAAAAAAA",
            target=target,
            routes=("/",),
            config=config,
            safety=safety,
            client=client,
            audit_log_path=tmp_path / "audit.log",
            env={},
        )
        result = run_xss_stored_check(ctx)
    finally:
        client.close()
    assert result.skipped is True


def test_sqli_inject_no_query_returns_none() -> None:
    assert _inject_into_query("http://x/", "p") is None


def test_sqli_error_baseline(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "security:\n  checks:\n    sqli: true\n"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, security_block=block, routes=("/?q=1",))
    result = run_sqli_check(ctx)
    assert result.skipped is False
    assert result.targets_scanned == 0


def test_idor_helpers() -> None:
    assert _candidate_segments("/static") == []
    assert _replace_segment("/users/42/profile", 1, "me") == "/users/me/profile"


def test_idor_token_lookup_via_env_dict(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "auth:\n  second_user:\n    token_env: TOKEN_X\n"
    ctx = make_ctx(auth_block=block, env={"TOKEN_X": "abc"})
    assert _second_user_token(ctx) == "abc"


def test_idor_skipped_when_no_id_segments(make_ctx) -> None:  # type: ignore[no-untyped-def]
    block = "auth:\n  second_user:\n    token_env: TOKEN_X\n"
    ctx = make_ctx(
        auth_block=block,
        env={"TOKEN_X": "abc"},
        routes=("/about",),
    )
    result = run_idor_check(ctx)
    assert result.targets_scanned == 0


def test_frontend_secrets_skips_data_url() -> None:
    urls = _bundle_urls(
        """<script src="data:text/javascript,alert(1)"></script>""",
        "http://x/",
    )
    assert urls == []


def test_frontend_secrets_loads_snapshot_with_garbage(tmp_path: Path) -> None:
    p = tmp_path / "snap.json"
    p.write_text("not json", encoding="utf-8")
    assert _load_snapshot(p) == {}


def test_frontend_secrets_snapshot_path_returns_none_when_missing(tmp_path: Path) -> None:
    assert _snapshot_path(tmp_path, "/") is None


def test_frontend_secrets_route_slug_helper() -> None:
    assert _route_slug("/") == "root"
    assert _route_slug("/api/users") == "api-users"


def test_frontend_secrets_unreachable_bundle(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, html="""<script src="/x.js"></script>""")
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_frontend_secrets_check(ctx)
    assert result.targets_scanned == 1


def test_scan_pii_skips_too_short_phone() -> None:
    assert scan_for_pii("call 555-1") == ()


def test_scan_secrets_handles_no_match() -> None:
    assert scan_for_secrets("nothing here") == ()


def test_has_reflection_returns_false_when_escaped_marker() -> None:
    body = "&lt;svg/onload=__SENTINELQA_XSS__&gt;"
    assert _has_reflection(body) is False


def _make_proof(path: Path) -> Path:
    now = datetime.now(UTC)
    payload = {
        "schema_version": "1",
        "host": "example.com",
        "actor": "tester",
        "scope": ["destructive"],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_sqli_proof_for_wrong_host_skips(tmp_path: Path) -> None:
    proof_path = _make_proof(tmp_path / "proof.yaml")
    cfg = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: https://other.example\n"
        "  allowed_hosts: [other.example]\n"
        f"  proof_of_authorization: {proof_path}\n"
        "security:\n"
        "  mode: authorized_destructive\n"
        "  checks:\n"
        "    sqli: true\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
        proof_of_authorization=config.target.proof_of_authorization,
    )
    safety = SafetyDecision(
        host="other.example",
        mode="authorized_destructive",
        allowed=True,
        reason="t",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(base_url="https://other.example", timeout=1.0)
    try:
        ctx = CheckContext(
            run_id="RUN-AAAAAAAAAAAA",
            target=target,
            routes=("/?q=1",),
            config=config,
            safety=safety,
            client=client,
            audit_log_path=tmp_path / "audit.log",
            env={},
        )
        result = run_sqli_check(ctx)
    finally:
        client.close()
    assert result.skipped is True


def test_parse_set_cookie_handles_empty() -> None:
    cookie = parse_set_cookie("")
    assert cookie.name == ""
