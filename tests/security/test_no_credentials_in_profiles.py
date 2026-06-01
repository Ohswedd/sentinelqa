"""AST guard: ``engine/auth/profiles/`` must not declare credential fields.

our engineering rules + §33 forbid SentinelQA from harvesting credentials.
Auth profiles are documentation; if a future contributor adds a field
named ``password`` / ``token`` / ``secret`` / ``key`` / ``credential`` /
``otp`` to :class:`engine.auth.profiles.AuthProfile` (or to any data
class declared inside ``engine/auth/profiles/``), this guard fails
fast at CI time — long before the structurally-credential-shaped value
could land in a vault file.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "engine" / "auth" / "profiles"

FORBIDDEN_NAME = re.compile(r"password|secret|token|key|credential|otp", re.IGNORECASE)

# Field names that SHOULD survive the guard even though they match the
# forbidden regex — the substring is part of a non-credential word
# (e.g. ``login_url_pattern`` is not a token).
_ALLOWED_FIELDS = {
    "name",
    "label",
    "login_url_pattern",
    "success_url_patterns",
    "mfa_hint",
    "tos_url",
    "category",
}


def _iter_class_fields() -> list[tuple[str, str]]:
    """Walk every dataclass/Pydantic field declared under ``profiles/``."""

    out: list[tuple[str, str]] = []
    for source_path in PROFILES_DIR.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        out.append((node.name, item.target.id))
                    elif isinstance(item, ast.Assign):
                        for tgt in item.targets:
                            if isinstance(tgt, ast.Name):
                                out.append((node.name, tgt.id))
    return out


def test_profiles_have_no_credential_fields() -> None:
    fields = _iter_class_fields()
    assert fields, "AST scan found no fields — has the profiles package moved?"
    offenders = []
    for klass, field in fields:
        if field in _ALLOWED_FIELDS:
            continue
        if FORBIDDEN_NAME.search(field):
            offenders.append((klass, field))
    assert not offenders, (
        f"engine/auth/profiles/ declares credential-shaped fields: {offenders}. "
        "SentinelQA never harvests credentials (our engineering rules + §33). "
        "If you have a legitimate non-credential field whose name happens to "
        "contain one of the forbidden words, add it to _ALLOWED_FIELDS in "
        "this guard."
    )


@pytest.mark.parametrize("forbidden", ["password", "secret", "token", "key", "credential", "otp"])
def test_forbidden_substrings_actually_trip_the_regex(forbidden: str) -> None:
    """Sanity-check the regex itself so the guard can't accidentally regress."""

    assert FORBIDDEN_NAME.search(forbidden)
