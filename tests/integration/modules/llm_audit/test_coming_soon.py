"""Integration tests for the coming-soon / placeholder-text check."""

from __future__ import annotations

from modules.llm_audit.checks.coming_soon import check_coming_soon
from modules.llm_audit.models import RenderedTextSample


def test_marketing_page_coming_soon_is_low() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/",
        text="Mobile app — coming soon!",
        priority="p3",
    )
    findings = check_coming_soon([sample])
    assert len(findings) == 1
    assert findings[0].severity_override == "low"


def test_authenticated_flow_is_medium() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/dashboard",
        text="Reports tab — TODO: hook up to API",
        is_authenticated_flow=True,
        priority="p2",
    )
    findings = check_coming_soon([sample])
    assert len(findings) == 1
    assert findings[0].severity_override == "medium"


def test_p0_flow_is_high() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/checkout",
        text="Payment step — coming soon",
        is_authenticated_flow=True,
        priority="p0",
    )
    findings = check_coming_soon([sample])
    assert len(findings) == 1
    assert findings[0].severity_override == "high"


def test_clean_text_is_silent() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/",
        text="Welcome back.",
    )
    assert check_coming_soon([sample]) == ()


def test_placeholder_word_is_flagged() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/profile",
        text="profile-placeholder",
        is_authenticated_flow=True,
        priority="p1",
    )
    findings = check_coming_soon([sample])
    assert len(findings) == 1
