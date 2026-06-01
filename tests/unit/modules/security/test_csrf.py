"""Unit tests for the CSRF check."""

from __future__ import annotations

import httpx

from modules.security.checks.csrf import (
    _form_has_csrf_token,
    _page_has_csrf_meta,
    _samesite_protects,
    run_csrf_check,
)


def test_form_with_csrf_input_is_recognized() -> None:
    body = """<form method="post"><input name="_token" value="x"><input name="email"></form>"""
    assert _form_has_csrf_token(body) is True


def test_form_without_token_returns_false() -> None:
    body = """<input name="email">"""
    assert _form_has_csrf_token(body) is False


def test_meta_csrf_token_recognized() -> None:
    html = '<meta name="csrf-token" content="abc">'
    assert _page_has_csrf_meta(html) is True


def test_samesite_lax_protects() -> None:
    assert _samesite_protects(["session=abc; SameSite=Lax"]) is True
    assert _samesite_protects(["session=abc"]) is False


def test_form_with_no_protection_yields_finding(make_ctx) -> None:  # type: ignore[no-untyped-def]
    body = """
        <html><body>
        <form method="post" action="/submit">
          <input name="email">
        </form>
        </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=body)

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_csrf_check(ctx)
    assert any(i.rule_id == "SEC-CSRF-MISSING-TOKEN" for i in result.issues)


def test_form_with_samesite_cookie_no_finding(make_ctx) -> None:  # type: ignore[no-untyped-def]
    body = """<form method="post" action="/submit"><input name="email"></form>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            html=body,
            headers=[("set-cookie", "session=abc; SameSite=Lax; HttpOnly")],
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_csrf_check(ctx)
    assert not any(i.rule_id == "SEC-CSRF-MISSING-TOKEN" for i in result.issues)


def test_get_form_not_flagged(make_ctx) -> None:  # type: ignore[no-untyped-def]
    body = """<form method="get" action="/search"><input name="q"></form>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html=body)

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/",))
    result = run_csrf_check(ctx)
    assert not any(i.rule_id == "SEC-CSRF-MISSING-TOKEN" for i in result.issues)
