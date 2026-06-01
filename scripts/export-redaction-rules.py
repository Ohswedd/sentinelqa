#!/usr/bin/env python
"""Emit ``packages/shared-schema/redaction-rules.json``.

Python is the **source of truth** for redaction. The TS
runtime mirrors the rules by loading this file. CI drift-checks the JSON
against the Python source by re-running this script and diffing.

The file is committed so the TS runtime never has to spawn Python to
build; ``--check`` mode (used by CI) writes nothing and exits non-zero
if the on-disk JSON is stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.policy.redaction import (
    _CATEGORY_FOR_KEY,
    _URL_SECRET_QUERY_KEYS,
    BUILTIN_RULES,
    SECRET_KEY_NAMES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "packages" / "shared-schema" / "redaction-rules.json"

# Bump when the shape of the JSON changes (not the rule contents).
RULES_SCHEMA_VERSION = "1.0.0"


def build_document() -> dict[str, object]:
    """Build the JSON payload, in canonical (sorted) order."""

    return {
        "schema_version": RULES_SCHEMA_VERSION,
        "description": (
            "SentinelQA redaction ruleset. Python (`engine.policy.redaction`) "
            "is the source of truth; this file mirrors it for the TS runtime. "
            "Edit Python first, then run `scripts/export-redaction-rules.py`."
        ),
        "secret_key_names": sorted(SECRET_KEY_NAMES),
        "category_for_key": dict(sorted(_CATEGORY_FOR_KEY.items())),
        "url_secret_query_keys": sorted(_URL_SECRET_QUERY_KEYS),
        "always_redact_headers": sorted(
            [
                "authorization",
                "proxy-authorization",
                "cookie",
                "set-cookie",
                "x-api-key",
                "api-key",
                "x-auth-token",
                "x-csrf-token",
                "x-xsrf-token",
            ]
        ),
        "value_rules": [
            {
                "category": rule.category,
                "pattern": rule.pattern.pattern,
                "flags": _flags_to_list(rule.pattern.flags),
                "description": rule.description,
            }
            for rule in BUILTIN_RULES
        ],
        "entropy": {
            "min_token_length": 32,
            "min_bits_per_char": 4.0,
            "pattern": r"[A-Za-z0-9_\-]{32,}",
        },
        "redacted_template": "[REDACTED:{category}]",
    }


def _flags_to_list(flags: int) -> list[str]:
    import re

    names = []
    if flags & re.IGNORECASE:
        names.append("IGNORECASE")
    if flags & re.MULTILINE:
        names.append("MULTILINE")
    if flags & re.DOTALL:
        names.append("DOTALL")
    return names


def _serialize(doc: dict[str, object]) -> str:
    return json.dumps(doc, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk file would change.",
    )
    args = parser.parse_args(argv)

    doc = build_document()
    rendered = _serialize(doc)

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} is missing; run scripts/export-redaction-rules.py", file=sys.stderr)
            return 1
        current = TARGET.read_text()
        if current != rendered:
            print(
                f"{TARGET} is stale. Run `python scripts/export-redaction-rules.py` to regenerate.",
                file=sys.stderr,
            )
            return 1
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
