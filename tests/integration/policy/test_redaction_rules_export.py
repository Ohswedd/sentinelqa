"""Phase 04.02 — Python is the redaction source of truth.

These checks guarantee that the JSON the TS runtime loads
(`packages/shared-schema/redaction-rules.json`) cannot drift from the
Python implementation in `engine.policy.redaction`. They cover two
failure modes:

1. The on-disk JSON is stale (Python changed; export script not re-run).
2. The JSON is missing fields that the TS side relies on.

CI runs both. The `--check` invocation of the export script is the
single load-bearing assertion; the field checks are guard-rails so a
future contributor can't quietly drop a section.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
JSON_PATH = REPO_ROOT / "packages" / "shared-schema" / "redaction-rules.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "export-redaction-rules.py"


def test_redaction_rules_json_exists() -> None:
    assert JSON_PATH.is_file(), f"missing: {JSON_PATH}"


def test_redaction_rules_json_is_current() -> None:
    """`--check` mode is the canonical drift gate; re-run to refresh."""

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"redaction-rules.json is stale. Stderr:\n{result.stderr}\n"
        f"Run `python scripts/export-redaction-rules.py` to refresh."
    )


@pytest.fixture(scope="module")
def doc() -> dict[str, object]:
    data: dict[str, object] = json.loads(JSON_PATH.read_text())
    return data


def test_required_fields_present(doc: dict[str, object]) -> None:
    for key in (
        "schema_version",
        "secret_key_names",
        "category_for_key",
        "url_secret_query_keys",
        "always_redact_headers",
        "value_rules",
        "entropy",
        "redacted_template",
    ):
        assert key in doc, f"missing top-level key: {key}"


def test_value_rules_have_pattern_and_category(doc: dict[str, object]) -> None:
    rules = doc["value_rules"]
    assert isinstance(rules, list)
    assert len(rules) >= 5
    for rule in rules:
        assert isinstance(rule, dict)
        assert "category" in rule
        assert "pattern" in rule
        assert "flags" in rule


def test_secret_key_names_sorted(doc: dict[str, object]) -> None:
    names = doc["secret_key_names"]
    assert isinstance(names, list)
    assert names == sorted(names), "secret_key_names must be canonically sorted"


def test_redacted_template_matches_python(doc: dict[str, object]) -> None:
    from engine.policy.redaction import _REDACTED_TEMPLATE

    assert doc["redacted_template"] == _REDACTED_TEMPLATE
