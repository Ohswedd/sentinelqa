"""Unit tests for the cookies check (Phase 13.03)."""

from __future__ import annotations

import httpx

from modules.security.checks.cookies import (
    evaluate_cookie,
    parse_set_cookie,
    run_cookies_check,
)


def _ids(issues) -> set[str]:
    return {i.rule_id for i in issues}


def test_parse_set_cookie_extracts_attributes() -> None:
    cookie = parse_set_cookie("sessionid=abc123; HttpOnly; Secure; SameSite=Lax; Path=/")
    assert cookie.name == "sessionid"
    assert "httponly" in cookie.attributes
    assert "secure" in cookie.attributes
    assert cookie.samesite == "lax"


def test_parse_set_cookie_handles_minimal_cookie() -> None:
    cookie = parse_set_cookie("bare=value")
    assert cookie.name == "bare"
    assert cookie.samesite is None
    assert "secure" not in cookie.attributes


def test_evaluate_auth_cookie_missing_secure_is_high() -> None:
    cookie = parse_set_cookie("session=abc")
    issues = list(evaluate_cookie(cookie, route="/login", is_https=True))
    high = [i for i in issues if i.severity == "high"]
    assert any(i.rule_id == "SEC-COOKIE-MISSING-SECURE" for i in high)
    assert any(i.rule_id == "SEC-COOKIE-MISSING-HTTPONLY" for i in high)
    assert any(i.rule_id == "SEC-COOKIE-MISSING-SAMESITE" for i in issues)


def test_evaluate_non_auth_cookie_severity_is_medium() -> None:
    cookie = parse_set_cookie("theme=dark")
    issues = list(evaluate_cookie(cookie, route="/", is_https=True))
    assert all(i.severity in {"medium", "low"} for i in issues)


def test_evaluate_samesite_none_without_secure_is_high() -> None:
    cookie = parse_set_cookie("session=abc; HttpOnly; SameSite=None")
    issues = list(evaluate_cookie(cookie, route="/", is_https=True))
    ids = _ids(issues)
    assert "SEC-COOKIE-SAMESITE-NONE-WITHOUT-SECURE" in ids


def test_evaluate_fully_protected_cookie_yields_nothing() -> None:
    # Phase 32 (ADR-0044): session cookies must also carry __Host- prefix.
    cookie = parse_set_cookie("__Host-session=abc; HttpOnly; Secure; SameSite=Strict; Path=/")
    assert list(evaluate_cookie(cookie, route="/", is_https=True)) == []


def test_evaluate_session_cookie_without_host_prefix_flags_phase32_rule() -> None:
    cookie = parse_set_cookie("session=abc; HttpOnly; Secure; SameSite=Strict; Path=/")
    issues = list(evaluate_cookie(cookie, route="/", is_https=True))
    ids = _ids(issues)
    assert "SEC-COOKIE-MISSING-PREFIX" in ids


def test_evaluate_overbroad_domain_fires() -> None:
    cookie = parse_set_cookie("session=abc; HttpOnly; Secure; SameSite=Lax; Domain=.example.com")
    issues = list(
        evaluate_cookie(
            cookie,
            route="/",
            is_https=True,
            response_host="app.example.com",
        )
    )
    ids = _ids(issues)
    assert "SEC-COOKIE-OVERBROAD-DOMAIN" in ids


def test_evaluate_overbroad_path_fires_on_auth_cookie() -> None:
    # No __Host- prefix → the Path=/ scope is genuinely over-broad for a
    # cookie clearly tied to /admin. __Host- prefix REQUIRES Path=/ so it's
    # excluded from this rule (see the explanatory comment in cookies.py).
    cookie = parse_set_cookie("admin_session=abc; HttpOnly; Secure; SameSite=Strict; Path=/")
    issues = list(evaluate_cookie(cookie, route="/admin", is_https=True))
    ids = _ids(issues)
    assert "SEC-COOKIE-OVERBROAD-PATH" in ids


def test_run_cookies_check_collects_findings(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[
                ("set-cookie", "sessionid=abc"),
                ("set-cookie", "theme=dark; HttpOnly; Secure"),
            ],
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_cookies_check(ctx)
    assert result.targets_scanned == 1
    # sessionid → missing HttpOnly + Secure + SameSite (3 issues).
    # theme → SameSite missing (1 issue).
    assert len(result.issues) >= 3
