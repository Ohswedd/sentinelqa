"""Structural smoke for the Next.js example."""

from __future__ import annotations

import json

from .conftest import EXAMPLES, load_example_config, read_text


def test_nextjs_layout_present() -> None:
    root = EXAMPLES / "nextjs"
    for marker in (
        "package.json",
        "next.config.mjs",
        "tsconfig.json",
        "README.md",
        "next-env.d.ts",
        "src/lib/auth.ts",
        "src/lib/db.ts",
        "src/middleware.ts",
        "src/app/layout.tsx",
        "src/app/globals.css",
        "src/app/page.tsx",
        "src/app/login/page.tsx",
        "src/app/signup/page.tsx",
        "src/app/dashboard/page.tsx",
        "src/app/projects/page.tsx",
        "src/app/projects/[id]/page.tsx",
        "src/app/admin/page.tsx",
        "src/app/api/auth/logout/route.ts",
        "src/app/api/health/route.ts",
    ):
        assert (root / marker).is_file(), marker


def test_nextjs_config_loads_with_full_module_set() -> None:
    cfg = load_example_config("nextjs")
    assert cfg.project.framework == "nextjs"
    assert str(cfg.target.base_url).startswith("http://127.0.0.1:3000")
    assert cfg.modules.functional is True
    assert cfg.modules.accessibility is True
    assert cfg.modules.security is True
    assert cfg.modules.llm_audit is True
    assert cfg.policy.min_quality_score == 85


def test_nextjs_package_pins_next_14() -> None:
    pkg = json.loads(read_text("nextjs", "package.json"))
    assert pkg["dependencies"]["next"].startswith("14."), pkg["dependencies"]["next"]
    assert pkg["dependencies"]["react"].startswith("18."), pkg["dependencies"]["react"]


def test_nextjs_security_headers_configured() -> None:
    cfg = read_text("nextjs", "next.config.mjs")
    # The README claims these headers; assert they live in the source.
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Content-Security-Policy",
    ):
        assert header in cfg, header


def test_nextjs_middleware_protects_private_routes() -> None:
    src = read_text("nextjs", "src", "middleware.ts")
    assert '"/projects"' in src
    assert '"/dashboard"' in src
    assert '"/admin"' in src
    assert "redirect" in src.lower()
