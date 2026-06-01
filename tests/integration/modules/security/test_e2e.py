"""End-to-end smoke for the security module.

Drives ``SecurityModule.run`` against an ``HTTPServer`` configured to
expose a deliberately-vulnerable fixture surface: missing security
headers, an auth cookie without ``HttpOnly``/``Secure``, a wildcard
CORS preflight, and a JS bundle containing a fake AWS key.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.domain.ids import IdGenerator
from engine.domain.target import Target
from engine.modules.base import ModuleContext
from engine.orchestrator.artifacts import ArtifactDirectory
from engine.policy.safety import SafetyDecision
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from modules.security import SecurityModule


def _build_ctx(
    tmp_path: Path,
    *,
    base_url: str,
) -> ModuleContext:
    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        f"  base_url: {base_url}\n"
        "  allowed_hosts: [localhost, 127.0.0.1]\n"
        "security:\n"
        "  checks:\n"
        "    dependency_scan: false\n"
        "    sast: false\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = ArtifactDirectory(run_dir)
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
        mode=config.security.mode,
    )
    safety = SafetyDecision(
        host="localhost",
        mode="safe",
        allowed=True,
        reason="e2e_fixture",
        decided_at=datetime.now(UTC),
    )
    return ModuleContext(
        module_name="security",
        config=config,
        safety_decision=safety,
        artifacts=artifacts,
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options={"routes": ("/", "/login")},
    )


def test_security_module_e2e_against_vulnerable_fixture(
    httpserver: HTTPServer,
    tmp_path: Path,
) -> None:
    def index_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            """<html><body><script src="/app.js"></script></body></html>""",
            status=200,
            headers={"Set-Cookie": "tracker=abc"},
        )

    def login_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            (
                "<html><body>"
                """<form method="post" action="/login">"""
                """<input name="email"></form>"""
                "</body></html>"
            ),
            status=200,
            headers={"Set-Cookie": "session=abc"},
        )

    def options_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            "",
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "true",
            },
        )

    def bundle_handler(request):  # type: ignore[no-untyped-def]
        return Response(
            "const cfg = { ak: 'AKIAIOSFODNN7EXAMPLE' };",
            status=200,
            content_type="application/javascript",
        )

    httpserver.expect_request("/").respond_with_handler(index_handler)
    httpserver.expect_request("/login", method="GET").respond_with_handler(login_handler)
    httpserver.expect_request("/login", method="OPTIONS").respond_with_handler(options_handler)
    httpserver.expect_request("/", method="OPTIONS").respond_with_handler(options_handler)
    httpserver.expect_request("/app.js").respond_with_handler(bundle_handler)

    ctx = _build_ctx(tmp_path, base_url=httpserver.url_for(""))
    module = SecurityModule(ctx.config, ctx.safety_decision)
    result = module.run(ctx)
    findings = result.findings
    rule_ids = {f.category.split("/")[-1] for f in findings}
    # We expect at minimum:
    # - csp_missing (headers)
    # - cookie httponly / secure (cookies)
    # - cors wildcard (cors)
    # - csrf missing token (csrf)
    # - frontend secret in bundle
    assert "sec-headers-csp-missing" in rule_ids
    assert "sec-cookie-missing-httponly" in rule_ids
    assert any("cors" in r for r in rule_ids)
    assert any("csrf" in r for r in rule_ids)
    assert any("frontend" in r for r in rule_ids)
    # Module status is "failed" (high/critical findings present).
    assert result.status == "failed"

    # Artifacts written.
    sec_dir = ctx.run_dir / "security"
    assert (sec_dir / "index.json").exists()
    assert (sec_dir / "headers.json").exists()


def test_security_module_safety_blocks_unsafe_target(
    tmp_path: Path,
) -> None:
    """A target outside the allowlist must trigger an :class:`UnknownHostError`."""

    from engine.errors.base import UnknownHostError

    cfg_text = (
        "version: 1\n"
        "project:\n  name: app\n"
        "target:\n"
        "  base_url: https://example.com\n"
        "  allowed_hosts: []\n"
    )
    (tmp_path / "sentinel.config.yaml").write_text(cfg_text, encoding="utf-8")
    config = load_config(tmp_path / "sentinel.config.yaml")
    target = Target(
        base_url=config.target.base_url,
        allowed_hosts=frozenset(config.target.allowed_hosts),
    )
    safety = SafetyDecision(
        host="example.com",
        mode="safe",
        allowed=True,
        reason="test_only_stub",
        decided_at=datetime.now(UTC),
    )
    run_dir = tmp_path / ".sentinel" / "runs" / "RUN-AAAAAAAAAAAA"
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = ModuleContext(
        module_name="security",
        config=config,
        safety_decision=safety,
        artifacts=ArtifactDirectory(run_dir),
        run_id="RUN-AAAAAAAAAAAA",
        run_dir=run_dir,
        target=target,
        id_generator=IdGenerator(),
        options={"routes": ("/",)},
    )
    module = SecurityModule(config, safety)
    with pytest.raises(UnknownHostError):
        module.validate_prerequisites(ctx)
