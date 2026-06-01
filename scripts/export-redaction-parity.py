#!/usr/bin/env python
"""Generate the cross-language redaction parity fixture.

The fixture (``tests/golden/redaction/parity.json``) is a list of
``{ id, kind, input, expected }`` records. ``kind`` is one of:

- ``string`` — feeds the input through :func:`redact_string` (the
 value-level pipeline). Byte-parity is required.
- ``value`` — feeds the input (already JSON) through :func:`redact`.
 Byte-parity is required.
- ``headers`` — feeds the input dict through :func:`redact_headers`.
 Byte-parity is required.

URL redaction is intentionally excluded: Python ``urlparse`` preserves
hostname case while JS ``URL`` normalises it, so byte-parity is
unreachable. The TS-side redactUrl tests are owned by the runtime.

Run modes:

 python scripts/export-redaction-parity.py # write the fixture
 python scripts/export-redaction-parity.py --check # fail if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engine.policy.redaction import (
    _redact_string,
    redact,
    redact_headers,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "tests" / "golden" / "redaction" / "parity.json"


# Curated inputs that exercise every rule family + the recursion path.
INPUTS: list[dict[str, Any]] = [
    # --- value-level (strings) ---
    {"id": "plain-text", "kind": "string", "input": "hello world"},
    {
        "id": "bearer-token",
        "kind": "string",
        "input": "Authorization: Bearer abc.DEF-ghi_jklmno0123456789",
    },
    {
        "id": "basic-auth",
        "kind": "string",
        "input": "Authorization: Basic dXNlcjpwYXNzd29yZA==",
    },
    {
        "id": "jwt",
        "kind": "string",
        "input": "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.deadbeef-cafebabe1234",
    },
    {
        "id": "aws-access-key-id",
        "kind": "string",
        "input": "aws_access_key_id=AKIAIOSFODNN7EXAMPLE",
    },
    {
        "id": "github-token",
        "kind": "string",
        "input": "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    },
    {
        "id": "slack-token",
        "kind": "string",
        "input": "SLACK=xoxb-1234567890-abcdef-XYZ",
    },
    {
        "id": "openai-key",
        "kind": "string",
        "input": "OPENAI_API_KEY=sk-abcdef1234567890ABCDEFabcdef1234",
    },
    {
        "id": "publishable-key",
        "kind": "string",
        "input": "STRIPE_PK=pk-abcdef1234567890ABCDEFabcdef1234",
    },
    {
        "id": "private-key",
        "kind": "string",
        "input": (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEAabcd...\n"
            "-----END RSA PRIVATE KEY-----"
        ),
    },
    {
        "id": "high-entropy-token",
        "kind": "string",
        "input": "session=Hb3KsP9w-jK4VqL0nx7Ze1QmRtUvY2Cd",
    },
    {
        "id": "no-secret",
        "kind": "string",
        "input": "the quick brown fox jumps over the lazy dog",
    },
    {
        "id": "gcp-service-account-marker",
        "kind": "string",
        "input": 'config: { "type": "service_account", "project_id": "foo" }',
    },
    # --- value-level (recursive structure) ---
    {
        "id": "value-dict-with-secrets",
        "kind": "value",
        "input": {
            "username": "alice",
            "password": "hunter2",
            "Authorization": "Bearer token-xyz-very-long-token-for-test-123",
            "extra": "ok",
        },
    },
    {
        "id": "value-nested-list",
        "kind": "value",
        "input": {
            "items": [
                {"api_key": "12345abcdef"},
                {"name": "no secret here"},
                {"Token": ""},  # empty value: should be left alone
            ],
            "deep": {"level2": {"set_cookie": "sid=xyz"}},
        },
    },
    {
        "id": "value-primitives",
        "kind": "value",
        "input": {"n": 42, "b": True, "x": None, "f": 1.5},
    },
    # --- headers ---
    {
        "id": "headers-mixed",
        "kind": "headers",
        "input": {
            "Authorization": "Bearer abc-def-ghi",
            "Cookie": "sid=abc123; csrftoken=xyz789",
            "Content-Type": "application/json",
            "X-Api-Key": "live_key_12345",
        },
    },
    {
        "id": "headers-non-secret",
        "kind": "headers",
        "input": {
            "Accept": "text/html",
            "Host": "example.com",
            "User-Agent": "sentinel-test/1.0",
        },
    },
]


def _expected(record: dict[str, Any]) -> Any:
    kind = record["kind"]
    raw = record["input"]
    if kind == "string":
        return _redact_string(raw)
    if kind == "value":
        return redact(raw)
    if kind == "headers":
        return redact_headers(raw)
    raise ValueError(f"unknown kind: {kind}")


def build_document() -> list[dict[str, Any]]:
    out = []
    for record in INPUTS:
        expected = _expected(record)
        out.append(
            {
                "id": record["id"],
                "kind": record["kind"],
                "input": record["input"],
                "expected": expected,
            }
        )
    return out


def _serialize(doc: list[dict[str, Any]]) -> str:
    return json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rendered = _serialize(build_document())

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} is missing", file=sys.stderr)
            return 1
        if TARGET.read_text() != rendered:
            print(
                f"{TARGET} is stale. "
                f"Run `python scripts/export-redaction-parity.py` to refresh.",
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
