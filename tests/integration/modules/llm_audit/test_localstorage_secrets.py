"""Integration tests for the localStorage / sessionStorage secrets check."""

from __future__ import annotations

from modules.llm_audit.checks.localstorage_secrets import check_localstorage_secrets
from modules.llm_audit.models import BrowserStorageSample


def test_jwt_in_localstorage_is_flagged() -> None:
    sample = BrowserStorageSample(
        route_url="http://localhost:3000/dashboard",
        store="localStorage",
        entries={
            "auth": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijklmnopqr",
        },
    )
    findings = check_localstorage_secrets([sample])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-CLIENT-SECRET-STORAGE"


def test_token_key_name_is_flagged_even_for_short_value() -> None:
    sample = BrowserStorageSample(
        route_url="http://localhost:3000/",
        store="sessionStorage",
        entries={"access_token": "shortbutstillatoken"},
    )
    findings = check_localstorage_secrets([sample])
    assert len(findings) == 1


def test_benign_value_is_silent() -> None:
    sample = BrowserStorageSample(
        route_url="http://localhost:3000/",
        store="localStorage",
        entries={"theme": "dark", "lastVisit": "2025-12-01"},
    )
    assert check_localstorage_secrets([sample]) == ()


def test_empty_value_is_silent() -> None:
    sample = BrowserStorageSample(
        route_url="http://localhost:3000/",
        store="localStorage",
        entries={"token": ""},
    )
    assert check_localstorage_secrets([sample]) == ()
