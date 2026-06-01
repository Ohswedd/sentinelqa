"""Unit tests for the reflected-XSS check."""

from __future__ import annotations

import httpx

from modules.security.checks.xss_reflected import (
    MARKER,
    PAYLOAD,
    _build_probed_url,
    _has_reflection,
    run_xss_reflected_check,
)


def test_build_probed_url_injects_query_when_missing() -> None:
    url, names = _build_probed_url("http://x/y", "PAYLOAD")
    assert "q=PAYLOAD" in url
    assert names == ["q"]


def test_build_probed_url_replaces_every_param() -> None:
    url, names = _build_probed_url("http://x/y?a=1&b=2", "P")
    assert "a=P" in url and "b=P" in url
    assert set(names) == {"a", "b"}


def test_has_reflection_detects_raw_marker_in_html() -> None:
    body = f"<html><body><svg/onload={MARKER}></body></html>"
    assert _has_reflection(body) is True


def test_has_reflection_ignores_escaped_marker() -> None:
    body = f"<html>&lt;svg/onload={MARKER}&gt;</html>"
    assert _has_reflection(body) is False


def test_has_reflection_returns_false_without_marker() -> None:
    assert _has_reflection("<html>no marker</html>") is False


def test_run_xss_reflected_flags_reflective_endpoint(make_ctx) -> None:  # type: ignore[no-untyped-def]
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        # Reflect the payload back unescaped.
        return httpx.Response(200, html=f"<html>echo: {PAYLOAD}</html>")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/search?q=hello",))
    result = run_xss_reflected_check(ctx)
    assert result.targets_scanned == 1
    high = [i for i in result.issues if i.severity == "high"]
    assert any(i.rule_id == "SEC-XSS-REFLECTED" for i in high)
    assert "q=" in captured[0]


def test_run_xss_reflected_no_finding_when_escaped(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        # Server HTML-escapes the marker — no finding expected.
        return httpx.Response(200, html=f"<html>echo: &lt;svg/onload={MARKER}&gt;</html>")

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/search?q=hello",))
    result = run_xss_reflected_check(ctx)
    assert result.issues == ()


def test_run_xss_reflected_confidence_reduced_when_csp_present(make_ctx) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            html=f"<html>echo: {PAYLOAD}</html>",
            headers={"content-security-policy": "default-src 'self'; script-src 'self'"},
        )

    transport = httpx.MockTransport(handler)
    ctx = make_ctx(transport=transport, routes=("/search?q=hi",))
    result = run_xss_reflected_check(ctx)
    assert result.issues
    issue = result.issues[0]
    assert issue.confidence <= 0.7
