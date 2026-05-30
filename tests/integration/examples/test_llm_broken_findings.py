"""Anti-pattern smoke for the LLM-broken example (Phase 26.06).

PRD §10.9 lists thirteen LLM-audit signal categories; Phase 26.06's
acceptance is "≥ 8 distinct LLM-audit findings". The LLM-audit module
itself is exercised end-to-end against the broken fixtures in
`tests/integration/modules/llm_audit/`; here we assert that the demo
example *itself* keeps demonstrating ≥ 8 of those anti-patterns so the
marketing demo and the audit cannot drift apart.
"""

from __future__ import annotations

from .conftest import EXAMPLES, load_example_config, read_text


def test_llm_broken_layout_present() -> None:
    root = EXAMPLES / "llm-broken"
    for marker in (
        "package.json",
        "next.config.mjs",
        "tsconfig.json",
        "README.md",
        "src/app/layout.tsx",
        "src/app/page.tsx",
        "src/app/login/page.tsx",
        "src/app/dashboard/page.tsx",
        "src/app/checkout/page.tsx",
        "src/app/admin/page.tsx",
    ):
        assert (root / marker).is_file(), marker


def test_llm_broken_config_does_not_gate_release() -> None:
    cfg = load_example_config("llm-broken")
    # The demo's purpose is to surface findings, not pass; the README documents
    # the explicit `min_quality_score: 0` so a careless audit doesn't pass.
    assert cfg.policy.min_quality_score == 0
    assert cfg.modules.llm_audit is True


def test_llm_broken_exhibits_at_least_eight_antipatterns() -> None:
    """Match against the deliberate anti-patterns wired into the demo.

    Each entry is (file, substring). We need >= 8 to match to satisfy
    Phase 26.06's acceptance criterion.
    """
    antipatterns: list[tuple[str, str]] = [
        # LLM-MOCK-DATA-SHIPPED
        (read_text("llm-broken", "src", "app", "page.tsx"), "MOCK_ORDERS"),
        # LLM-DEAD-BTN (page.tsx)
        (read_text("llm-broken", "src", "app", "page.tsx"), "<button type=\"button\">Save</button>"),
        # LLM-DEAD-BTN (checkout)
        (
            read_text("llm-broken", "src", "app", "checkout", "page.tsx"),
            "<button type=\"button\">Place order</button>",
        ),
        # LLM-CONSOLE-ERROR-IGNORED
        (read_text("llm-broken", "src", "app", "page.tsx"), "swallowed console error"),
        # LLM-HARDCODED-CRED
        (read_text("llm-broken", "src", "app", "login", "page.tsx"), "ADMIN_PASSWORD"),
        # LLM-UI-ONLY-AUTH + frontend-signed JWT
        (read_text("llm-broken", "src", "app", "login", "page.tsx"), "btoa(JSON.stringify"),
        # LLM-CLIENT-SECRET-STORAGE
        (
            read_text("llm-broken", "src", "app", "login", "page.tsx"),
            'window.localStorage.setItem("jwt"',
        ),
        # LLM-NO-LOADING-STATE / LLM-NO-ERROR-STATE / LLM-UNHANDLED-PROMISE
        (read_text("llm-broken", "src", "app", "dashboard", "page.tsx"), 'fetch("/api/orders")'),
        # LLM-FAKE-ENDPOINT: dashboard hits /api/orders but the example ships
        # no route.ts for it.
        # LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS
        (read_text("llm-broken", "src", "app", "checkout", "page.tsx"), "validateEmail"),
        # LLM-PLACEHOLDER-TEXT
        (read_text("llm-broken", "src", "app", "checkout", "page.tsx"), "Coming soon"),
    ]
    matches = [needle for haystack, needle in antipatterns if needle in haystack]
    assert len(matches) >= 8, (
        f"only {len(matches)} anti-patterns matched: "
        + ", ".join(repr(m) for m in matches)
    )


def test_llm_broken_has_no_orders_api_route() -> None:
    """LLM-FAKE-ENDPOINT — dashboard fetches /api/orders but no handler ships."""
    orders_route = EXAMPLES / "llm-broken" / "src" / "app" / "api" / "orders" / "route.ts"
    assert not orders_route.exists(), (
        f"{orders_route} exists; the demo's LLM-FAKE-ENDPOINT signal requires "
        "the dashboard to fetch a route that has no server-side handler."
    )


def test_llm_broken_readme_warns_do_not_deploy() -> None:
    readme = read_text("llm-broken", "README.md")
    lowered = readme.lower()
    assert "do not deploy" in lowered
    assert "intentionally broken" in lowered
