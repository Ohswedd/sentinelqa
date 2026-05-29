"""Integration tests for the mock-data check (task 19.04)."""

from __future__ import annotations

from modules.llm_audit.checks.mock_data import (
    check_mock_data_in_bundles,
    check_mock_data_in_rendered_text,
)
from modules.llm_audit.models import BundleSnippet, RenderedTextSample


def test_mock_data_export_is_flagged() -> None:
    snippet = BundleSnippet(
        path="src/app.js",
        body="const banner = 'hi';\nexport const mockData = [1, 2, 3];\n",
    )
    findings = check_mock_data_in_bundles([snippet])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-MOCK-DATA-SHIPPED"
    assert findings[0].file == "src/app.js"
    assert findings[0].line == 2


def test_mock_data_import_is_flagged() -> None:
    snippet = BundleSnippet(
        path="src/data.js",
        body="import users from './mock.json';\n",
    )
    findings = check_mock_data_in_bundles([snippet])
    assert len(findings) == 1


def test_clean_bundle_is_silent() -> None:
    snippet = BundleSnippet(
        path="src/app.js",
        body="const real = fetch('/api/users');\n",
    )
    assert check_mock_data_in_bundles([snippet]) == ()


def test_rendered_text_flags_placeholder_user() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/users",
        text="Hello John Doe! Your dashboard awaits.",
    )
    findings = check_mock_data_in_rendered_text([sample])
    assert len(findings) == 1
    assert findings[0].severity_override == "medium"


def test_rendered_text_in_authenticated_flow_is_high() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/dashboard",
        text="Welcome jane@example.com",
        is_authenticated_flow=True,
    )
    findings = check_mock_data_in_rendered_text([sample])
    assert len(findings) == 1
    assert findings[0].severity_override == "high"


def test_legitimate_text_is_silent() -> None:
    sample = RenderedTextSample(
        route_url="http://localhost:3000/",
        text="Welcome back, Alex.",
    )
    assert check_mock_data_in_rendered_text([sample]) == ()
