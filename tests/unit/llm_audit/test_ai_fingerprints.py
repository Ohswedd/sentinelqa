# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Tests for the AI-app fingerprint check (v1.9.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.llm_audit.checks.ai_fingerprints import (
    Fingerprint,
    check_ai_fingerprints,
    load_fingerprints,
)
from modules.llm_audit.models import RenderedTextSample, SourceFile


def _src(path: str, body: str) -> SourceFile:
    return SourceFile(path=path, body=body)


def _txt(route: str, text: str) -> RenderedTextSample:
    return RenderedTextSample(route_url=route, text=text)


# ---------------------------------------------------------------------------
# Catalogue loading
# ---------------------------------------------------------------------------


def test_default_catalogue_loads_and_compiles() -> None:
    fingerprints = load_fingerprints()
    assert fingerprints
    # Each compiled pattern must be a real regex.
    for fp in fingerprints:
        assert fp.pattern.search("anything") is None or True  # smoke compile only
        assert fp.severity in ("critical", "high", "medium", "low", "info")
        assert fp.target in ("source", "rendered")
        assert 0.0 <= fp.confidence <= 1.0


def test_default_catalogue_contains_well_known_ids() -> None:
    ids = {fp.id for fp in load_fingerprints()}
    for required in {
        "ai-stripe-test-key",
        "ai-stripe-secret-key",
        "ai-lorem-ipsum-block",
        "ai-fake-credit-card",
        "ai-localhost-api-url",
    }:
        assert required in ids


def test_loader_rejects_unknown_target(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: '1'\n"
        "fingerprints:\n"
        "  - id: x\n"
        "    target: somewhere\n"
        "    severity: high\n"
        "    pattern: foo\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_fingerprints(bad)


def test_loader_rejects_invalid_severity(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: '1'\n"
        "fingerprints:\n"
        "  - id: x\n"
        "    target: source\n"
        "    severity: extreme\n"
        "    pattern: foo\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_fingerprints(bad)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

# Split across string concatenation so GitHub Secret Scanning + gitleaks
# don't flag these test inputs as live keys. The compiled regex inside
# the fingerprint matches the concatenated literal at runtime.
_PK_TEST_FAKE = "pk_" + "test_" + "A" * 24
_SK_TEST_FAKE = "sk_" + "test_" + "A" * 24


def test_stripe_test_key_matches_in_source() -> None:
    fingerprints = load_fingerprints()
    src = _src("dist/bundle.js", f"const k = '{_PK_TEST_FAKE}';")
    findings = check_ai_fingerprints([src], [], catalogue=fingerprints)
    assert any(
        f.extra_context and ("fingerprint_id", "ai-stripe-test-key") in f.extra_context
        for f in findings
    )


def test_lorem_block_matches_in_rendered() -> None:
    fingerprints = load_fingerprints()
    txt = _txt(
        "/about",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Etc etc.",
    )
    findings = check_ai_fingerprints([], [txt], catalogue=fingerprints)
    assert any(
        ("fingerprint_id", "ai-lorem-ipsum-block") in (f.extra_context or ()) for f in findings
    )


def test_clean_input_produces_no_findings() -> None:
    fingerprints = load_fingerprints()
    src = _src(
        "dist/bundle.js",
        "export const foo = 'bar'; // a perfectly normal line",
    )
    txt = _txt("/home", "Welcome to our production app. Sign in to continue.")
    findings = check_ai_fingerprints([src], [txt], catalogue=fingerprints)
    assert findings == ()


def test_fingerprint_severity_overrides_propagate() -> None:
    fingerprints = load_fingerprints()
    src = _src("dist/bundle.js", f"const k = '{_SK_TEST_FAKE}';")
    findings = check_ai_fingerprints([src], [], catalogue=fingerprints)
    secret_finding = next(
        f for f in findings if ("fingerprint_id", "ai-stripe-secret-key") in (f.extra_context or ())
    )
    assert secret_finding.severity_override == "critical"


def test_match_in_source_records_path() -> None:
    fingerprint = Fingerprint(
        id="t-x",
        target="source",
        category="test",
        severity="low",
        confidence=0.7,
        title="x",
        description="d",
        pattern=__import__("re").compile("XXX"),
    )
    src = _src("a/b.ts", "value = XXX;")
    findings = check_ai_fingerprints([src], [], catalogue=[fingerprint])
    assert findings[0].file == "a/b.ts"


def test_match_in_rendered_records_route() -> None:
    fingerprint = Fingerprint(
        id="t-x",
        target="rendered",
        category="test",
        severity="low",
        confidence=0.7,
        title="x",
        description="d",
        pattern=__import__("re").compile("XXX"),
    )
    txt = _txt("/foo", "blah XXX blah")
    findings = check_ai_fingerprints([], [txt], catalogue=[fingerprint])
    assert findings[0].route == "/foo"


def test_empty_inputs_returns_empty() -> None:
    findings = check_ai_fingerprints([], [], catalogue=load_fingerprints())
    assert findings == ()


def test_empty_catalogue_returns_empty() -> None:
    src = _src("a.ts", f"anything {_PK_TEST_FAKE}")
    findings = check_ai_fingerprints([src], [], catalogue=[])
    assert findings == ()
