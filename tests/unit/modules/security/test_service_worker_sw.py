# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for the service-worker audit."""

from __future__ import annotations

from modules.security.checks.service_worker import (
    ServiceWorkerInfo,
    detect_service_worker,
    evaluate_service_worker,
)


def test_detect_finds_register_call() -> None:
    html = "<script>navigator.serviceWorker.register('/sw.js')</script>"
    info = detect_service_worker(html)
    assert info.registered
    assert info.script_url == "/sw.js"


def test_detect_finds_register_with_scope() -> None:
    html = """<script>
        navigator.serviceWorker.register('/sw.js', { scope: '/app/' });
    </script>"""
    info = detect_service_worker(html)
    assert info.registered
    assert info.scope == "/app/"


def test_detect_returns_unregistered_when_absent() -> None:
    info = detect_service_worker("<html><body>nothing</body></html>")
    assert info.registered is False


def test_evaluate_returns_nothing_when_unregistered() -> None:
    findings = evaluate_service_worker(
        ServiceWorkerInfo(registered=False),
        page_origin="https://app.example.com",
    )
    assert findings == ()


def test_eager_push_prompt_flagged() -> None:
    html = "Notification.requestPermission()"
    findings = evaluate_service_worker(
        ServiceWorkerInfo(registered=True, script_url="/sw.js"),
        page_origin="https://app.example.com",
        page_html_for_push_check=html,
    )
    assert any(f.code == "SW-PUSH-PROMPT-EAGER" for f in findings)


def test_risky_strategy_on_sensitive_path_flagged() -> None:
    info = ServiceWorkerInfo(
        registered=True,
        script_url="/sw.js",
        script_body=(
            "import { registerRoute } from 'workbox';\n"
            'registerRoute("/api/me", new CacheFirst());\n'
        ),
    )
    findings = evaluate_service_worker(info, page_origin="https://app.example.com")
    codes = {f.code for f in findings}
    assert "SW-CACHE-SENSITIVE" in codes


def test_safe_strategy_does_not_flag() -> None:
    info = ServiceWorkerInfo(
        registered=True,
        script_url="/sw.js",
        script_body="registerRoute('/api/me', new NetworkOnly());",
    )
    findings = evaluate_service_worker(info, page_origin="https://app.example.com")
    assert all(f.code != "SW-CACHE-SENSITIVE" for f in findings)


def test_narrow_scope_flagged_as_low() -> None:
    info = ServiceWorkerInfo(
        registered=True,
        script_url="/sw.js",
        scope="/very/deep/sub/scope/",
    )
    findings = evaluate_service_worker(info, page_origin="https://app.example.com")
    assert any(f.code == "SW-SCOPE-TOO-NARROW" for f in findings)
