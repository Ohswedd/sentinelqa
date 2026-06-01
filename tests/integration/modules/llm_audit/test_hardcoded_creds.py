"""Integration tests for the hardcoded-credentials scanner (task 19.08).

Per our engineering rules, the test asserts that the persisted snippet has the
literal credential redacted before leaving the function.
"""

from __future__ import annotations

from modules.llm_audit.checks.hardcoded_creds import check_hardcoded_credentials
from modules.llm_audit.models import SourceFile


def test_demo_admin_pair_is_flagged() -> None:
    src = SourceFile(
        path="src/seed.js",
        body=(
            "const admin = {\n"
            "  email: 'admin@example.com',\n"
            "  password: 'CorrectHorseBattery'\n"
            "};\n"
        ),
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)
    snippets = " ".join(f.snippet or "" for f in findings)
    # The literal must be redacted.
    assert "CorrectHorseBattery" not in snippets
    assert "REDACTED" in snippets


def test_jwt_literal_is_flagged_and_redacted() -> None:
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijklmnopqr"
    src = SourceFile(
        path="src/auth.js",
        body=f"const t = '{fake_jwt}';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)
    snippets = " ".join(f.snippet or "" for f in findings)
    assert fake_jwt not in snippets


def test_postgres_connection_string_is_flagged() -> None:
    src = SourceFile(
        path="config/db.js",
        body="export const url = 'postgres://user:hunter2@db:5432/app';\n",
    )
    findings = check_hardcoded_credentials([src])
    assert any(f.rule_id == "LLM-HARDCODED-CRED" for f in findings)
    snippets = " ".join(f.snippet or "" for f in findings)
    assert "hunter2" not in snippets


def test_clean_source_is_silent() -> None:
    src = SourceFile(
        path="src/app.js",
        body="const url = process.env.DATABASE_URL;\n",
    )
    assert check_hardcoded_credentials([src]) == ()
