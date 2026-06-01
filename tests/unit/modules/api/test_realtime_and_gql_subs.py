# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for WebSocket/SSE and GraphQL subscription checks."""

from __future__ import annotations

from modules.api.checks.graphql_subscriptions import (
    SubscriptionDefinition,
    SubscriptionSession,
    evaluate_subscription_auth,
    evaluate_subscription_session,
    parse_subscriptions,
)
from modules.api.checks.realtime import (
    RealtimeEndpoint,
    detect_sse_endpoints,
    detect_websocket_endpoints,
    evaluate_sse_endpoint,
    evaluate_websocket_handshake,
)

# --------------------------------------------------------------------------- #
# Realtime detection
# --------------------------------------------------------------------------- #


def test_detect_websocket_endpoints_in_html() -> None:
    html = '<script>const sock = new WebSocket("wss://api.example.com/realtime");</script>'
    endpoints = detect_websocket_endpoints(html, page_origin="https://app.example.com")
    assert len(endpoints) == 1
    assert endpoints[0].url.startswith("wss://")


def test_detect_websocket_dedups_repeats_across_blobs() -> None:
    html = '<script>connect("wss://api.example.com/s")</script>'
    bundle = 'open("wss://api.example.com/s")'
    endpoints = detect_websocket_endpoints(html, (bundle,), page_origin="https://app.example.com")
    assert len(endpoints) == 1


def test_detect_sse_endpoints() -> None:
    html = "<script>new EventSource('/api/stream')</script>"
    endpoints = detect_sse_endpoints(html, page_origin="https://app.example.com")
    assert len(endpoints) == 1
    assert endpoints[0].url == "/api/stream"


# --------------------------------------------------------------------------- #
# WebSocket handshake evaluation
# --------------------------------------------------------------------------- #


_WS_ENDPOINT = RealtimeEndpoint(
    kind="websocket",
    url="wss://api.example.com/realtime",
    origin="https://app.example.com",
)


def test_cross_origin_ws_handshake_is_high() -> None:
    findings = evaluate_websocket_handshake(
        _WS_ENDPOINT,
        accepted_origin=True,
        enforces_origin=False,
        allows_unbounded_messages=None,
        requires_auth=None,
    )
    assert any(f.code == "WS-CROSS-ORIGIN-ACCEPTED" and f.severity == "high" for f in findings)


def test_ws_unauthenticated_handshake_is_high() -> None:
    findings = evaluate_websocket_handshake(
        _WS_ENDPOINT,
        accepted_origin=False,
        enforces_origin=True,
        allows_unbounded_messages=None,
        requires_auth=False,
    )
    assert any(f.code == "WS-NO-AUTH" for f in findings)


def test_ws_unbounded_messages_is_medium() -> None:
    findings = evaluate_websocket_handshake(
        _WS_ENDPOINT,
        accepted_origin=False,
        enforces_origin=True,
        allows_unbounded_messages=True,
        requires_auth=True,
    )
    assert any(f.code == "WS-NO-MESSAGE-LIMIT" for f in findings)


# --------------------------------------------------------------------------- #
# SSE evaluation
# --------------------------------------------------------------------------- #


_SSE_ENDPOINT = RealtimeEndpoint(
    kind="sse",
    url="/api/stream",
    origin="https://app.example.com",
)


def test_sse_short_reconnect_flagged() -> None:
    findings = evaluate_sse_endpoint(
        _SSE_ENDPOINT,
        auto_reconnect_seconds=0.2,
        sends_last_event_id=None,
    )
    assert any(f.code == "SSE-RECONNECT-STORM" for f in findings)


def test_sse_no_last_event_id_flagged() -> None:
    findings = evaluate_sse_endpoint(
        _SSE_ENDPOINT,
        auto_reconnect_seconds=None,
        sends_last_event_id=False,
    )
    assert any(f.code == "SSE-NO-LAST-EVENT-ID" for f in findings)


# --------------------------------------------------------------------------- #
# GraphQL subscription parsing
# --------------------------------------------------------------------------- #


def test_parse_subscriptions_returns_each_field() -> None:
    sdl = """
    type Subscription {
        userUpdated(userId: ID!): User
        orderStatus: OrderStatus @auth
    }
    """
    fields = parse_subscriptions(sdl)
    assert len(fields) == 2
    names = {f.name for f in fields}
    assert names == {"userUpdated", "orderStatus"}


def test_parse_subscriptions_detects_auth_directive() -> None:
    sdl = "type Subscription { secret: String @auth }"
    fields = parse_subscriptions(sdl)
    assert fields[0].has_directive_auth is True


def test_evaluate_subscription_auth_flags_unauthenticated() -> None:
    definition = SubscriptionDefinition(name="firehose", return_type="Event")
    findings = evaluate_subscription_auth(definition)
    assert len(findings) == 1
    assert findings[0].code == "GQL-SUB-NO-AUTH"


def test_evaluate_subscription_auth_returns_nothing_when_directive_present() -> None:
    definition = SubscriptionDefinition(name="secure", return_type="Event", has_directive_auth=True)
    assert evaluate_subscription_auth(definition) == ()


def test_evaluate_subscription_session_flags_anon_handshake() -> None:
    session = SubscriptionSession(
        subscription_name="news",
        accepted_unauthenticated=True,
        messages_per_second=10,
        payload_caps_in_kib=64,
        rate_limited=True,
    )
    findings = evaluate_subscription_session(session)
    assert any(f.code == "GQL-SUB-ANON-ACCEPTED" and f.severity == "critical" for f in findings)


def test_evaluate_subscription_session_flags_high_message_rate() -> None:
    session = SubscriptionSession(
        subscription_name="firehose",
        accepted_unauthenticated=False,
        messages_per_second=250,
        payload_caps_in_kib=128,
        rate_limited=True,
    )
    findings = evaluate_subscription_session(session)
    assert any(f.code == "GQL-SUB-HIGH-RATE" for f in findings)


def test_evaluate_subscription_session_flags_uncapped_payload() -> None:
    session = SubscriptionSession(
        subscription_name="x",
        accepted_unauthenticated=False,
        messages_per_second=10,
        payload_caps_in_kib=None,
        rate_limited=True,
    )
    findings = evaluate_subscription_session(session)
    assert any(f.code == "GQL-SUB-NO-PAYLOAD-CAP" for f in findings)


def test_evaluate_subscription_session_flags_no_rate_limit() -> None:
    session = SubscriptionSession(
        subscription_name="x",
        accepted_unauthenticated=False,
        messages_per_second=10,
        payload_caps_in_kib=128,
        rate_limited=False,
    )
    findings = evaluate_subscription_session(session)
    assert any(f.code == "GQL-SUB-NO-RATE-LIMIT" for f in findings)
