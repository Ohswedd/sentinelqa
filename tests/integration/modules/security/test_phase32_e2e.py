"""End-to-end integration tests for the Phase-32 checks.

These tests exercise the public ``run_*_check`` entry points against a
controlled :class:`httpx.MockTransport` instead of a real network. The
goal is to prove the I/O paths handle realistic response shapes (not
just the pure classifier functions covered by the unit tests).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
from engine.config.loader import load_config
from engine.domain.target import Target
from engine.policy.safety import SafetyDecision

from modules.security.checks.api_bola_bfla import (
    CapturedCall,
    ReplayHeaders,
)
from modules.security.checks.bundle_secrets import run_bundle_secrets_check
from modules.security.checks.context import CheckContext
from modules.security.checks.frontend_only_auth_deeper import (
    ObservedEndpoint,
    run_frontend_only_auth_deeper_check,
)
from modules.security.checks.graphql_safety import run_graphql_safety_check
from modules.security.checks.jwt_weakness import run_jwt_weakness_check
from modules.security.checks.ssrf_redirect import UrlInput
from modules.security.checks.tls_posture import (
    TlsHandshakeResult,
    run_tls_posture_check,
)


def _config_path(tmp_path: Path, *, base_url: str = "http://localhost:8088") -> Path:
    cfg = tmp_path / "sentinel.config.yaml"
    cfg.write_text(
        "version: 1\nproject:\n  name: app\n"
        f"target:\n  base_url: {base_url}\n"
        "  allowed_hosts: [localhost, 127.0.0.1, api.example.test]\n",
        encoding="utf-8",
    )
    return cfg


def _make_ctx(
    tmp_path: Path,
    *,
    transport: httpx.BaseTransport,
    base_url: str = "http://localhost:8088",
    mode: str = "safe",
    proof_of_authorization: str | None = None,
    env: dict[str, str] | None = None,
) -> CheckContext:
    cfg = _config_path(tmp_path, base_url=base_url)
    config = load_config(cfg)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=mode,
        proof_of_authorization=Path(proof_of_authorization) if proof_of_authorization else None,
    )
    safety = SafetyDecision(
        host="localhost",
        mode=mode,
        allowed=True,
        reason="test_fixture",
        decided_at=datetime.now(UTC),
    )
    client = httpx.Client(base_url=base_url, transport=transport, timeout=5.0)
    return CheckContext(
        run_id="RUN-AAAAAAAAAAAA",
        target=target,
        routes=("/",),
        config=config,
        safety=safety,
        client=client,
        audit_log_path=tmp_path / "audit.log",
        env=env or {},
    )


# ---------------- JWT (32.01) ----------------


def test_jwt_check_picks_up_alg_none_observation(tmp_path: Path) -> None:
    import base64
    import json

    def _b64(payload: bytes) -> str:
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")

    header = _b64(json.dumps({"alg": "none"}).encode("utf-8"))
    payload = _b64(json.dumps({"sub": "alice"}).encode("utf-8"))
    token = f"{header}.{payload}."

    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    try:
        observations = (("header:authorization", f"Bearer {token}"),)
        result = run_jwt_weakness_check(ctx, observations=observations, now=1_700_000_000.0)
        assert any(i.rule_id == "SEC-JWT-ALG-NONE" for i in result.issues)
    finally:
        ctx.client.close()


# ---------------- TLS posture (32.03) ----------------


def test_tls_posture_skips_on_non_https_target(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    try:
        result = run_tls_posture_check(ctx)
        assert result.skipped
        assert "non-https" in (result.skipped_reason or "")
    finally:
        ctx.client.close()


def test_tls_posture_runs_with_injected_handshake(tmp_path: Path) -> None:
    ctx = _make_ctx(
        tmp_path,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
        base_url="https://api.example.test:8443",
    )

    def fake_probe(host: str, port: int) -> TlsHandshakeResult:
        return TlsHandshakeResult(
            host=host,
            port=port,
            tls_version="TLSv1",
            cipher_name="ECDHE-RSA-RC4-SHA",
            cipher_bits=128,
            leaf_subject_cn=host,
            leaf_issuer_cn="Test CA",
            not_before=datetime.now(UTC),
            not_after=datetime.now(UTC),
            san=(host,),
            fingerprint_sha256="0" * 64,
            hsts_header=None,
        )

    try:
        result = run_tls_posture_check(ctx, probe=fake_probe)
        ids = {i.rule_id for i in result.issues}
        assert "SEC-TLS-VERSION-LEGACY" in ids
        assert "SEC-TLS-WEAK-CIPHER" in ids
        assert "SEC-TLS-HSTS-MISSING" in ids
    finally:
        ctx.client.close()


# ---------------- GraphQL (32.04) ----------------


def test_graphql_safety_e2e_against_mock(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Server returns data for every introspection-shaped query.
        return httpx.Response(200, json={"data": {"__schema": {"types": []}}})

    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(handler))
    try:
        result = run_graphql_safety_check(
            ctx,
            endpoints=("/graphql",),
            mutations=("deleteUser",),
        )
        ids = {i.rule_id for i in result.issues}
        assert "SEC-GRAPHQL-INTROSPECTION-ENABLED" in ids
        assert "SEC-GRAPHQL-MUTATION-NO-AUTH" in ids
    finally:
        ctx.client.close()


def test_graphql_safety_skips_when_no_endpoints(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(lambda _r: httpx.Response(404)))
    try:
        result = run_graphql_safety_check(ctx, endpoints=())
        assert result.skipped
    finally:
        ctx.client.close()


# ---------------- BOLA/BFLA (32.05) ----------------
#
# BOLA's destructive-mode + proof-of-authorization gate is exercised by
# the dedicated tests under ``tests/security/test_bola_requires_*.py``;
# the inner replay/classification logic is covered by the unit tests
# in ``tests/unit/modules/security/test_api_bola_bfla.py``. We add one
# integration test here that exercises the pure-classification path
# directly against an httpx MockTransport so the full
# ``classify_replay`` → ``evaluate_classification`` chain is covered.


def test_bola_classifier_chain_against_mock(tmp_path: Path) -> None:
    from modules.security.checks.api_bola_bfla import (
        classify_replay,
        evaluate_classification,
        replay_call,
    )

    captured = CapturedCall(
        method="GET",
        url="http://localhost:8088/users/42",
        body_shape=("email", "id"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 42, "email": "alice@example.com"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        status, body = replay_call(
            client,
            captured,
            ReplayHeaders(identity_a={}, identity_b={"Authorization": "Bearer B"}),
        )
        classification = classify_replay(captured, status, body, b_is_admin=False)
        assert classification == "bola"
        issues = list(evaluate_classification(captured, classification))
        assert any(i.rule_id == "SEC-BOLA-CROSS-TENANT-READ" for i in issues)
    finally:
        client.close()


# ---------------- Frontend-only-auth deeper (32.06) ----------------


def test_frontend_only_auth_deeper_flags_open_endpoint(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"emails": ["alice@example.com"]})

    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(handler))
    try:
        result = run_frontend_only_auth_deeper_check(
            ctx,
            observed_endpoints=(
                ObservedEndpoint(
                    method="GET",
                    url="http://localhost:8088/api/users/me",
                    saw_payload_when_authenticated=True,
                ),
            ),
        )
        assert any(i.rule_id == "SEC-IDOR-CROSS-USER-ACCESS" for i in result.issues)
    finally:
        ctx.client.close()


# ---------------- Bundle secrets (32.07) ----------------


def test_bundle_secrets_streams_and_redacts(tmp_path: Path) -> None:
    bundle = (
        b'const k = "AKIAIOSFODNN7EXAMPLE"; var t = "ghp_ABCdefGHIjklMNOpqrSTUvwxYZ0123456789";'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=bundle,
            headers={"content-type": "application/javascript"},
        )

    ctx = _make_ctx(tmp_path, transport=httpx.MockTransport(handler))
    try:
        result = run_bundle_secrets_check(
            ctx,
            bundle_urls=("http://localhost:8088/static/main.js",),
        )
        ids = {i.rule_id for i in result.issues}
        assert "SEC-BUNDLE-SECRET-AWS" in ids
        assert "SEC-BUNDLE-SECRET-GITHUB" in ids
        # No raw secret in the persisted issue evidence.
        for issue in result.issues:
            assert "AKIAIOSFODNN7EXAMPLE" not in str(issue.evidence)
    finally:
        ctx.client.close()


# ---------------- SSRF / open-redirect (32.08) ----------------
#
# SSRF's destructive-mode + proof-of-authorization gate is exercised by
# ``tests/security/test_ssrf_requires_authorization.py``; the
# classifier logic is covered by
# ``tests/unit/modules/security/test_ssrf_redirect.py``. The
# integration test below proves the SSRF + redirect classifier chain
# against a controlled httpx transport, without going through the
# safety policy enforcement (which is already verified in the
# dedicated gating tests).


def test_ssrf_classifier_chain_against_mock(tmp_path: Path) -> None:
    from modules.security.checks.ssrf_redirect import (
        _send_payload,
        classify_redirect_response,
        classify_ssrf_response,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        payload = params.get("url", "")
        if "169.254" in payload:
            return httpx.Response(200, text="imds-token: aws.creds")
        if "//attacker" in payload:
            return httpx.Response(302, headers={"location": "//attacker.example.com"})
        return httpx.Response(400, text="invalid url")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    input_ = UrlInput(method="GET", url="http://localhost:8088/proxy", parameter="url")
    try:
        # SSRF-shaped payload — server returns 200 with imds-like body.
        status, body, _ = _send_payload(client, input_, "http://169.254.169.254/")
        assert classify_ssrf_response(status, body) == "ssrf_suspected"
        # Open-redirect payload — server emits 30x with attacker location.
        status, _body, location = _send_payload(client, input_, "//attacker.example.com")
        assert classify_redirect_response(status, location) == "open_redirect"
    finally:
        client.close()
