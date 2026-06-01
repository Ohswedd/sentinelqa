"""the engineering guidelines: every product output of the performance module must
label its measurements as *synthetic*, and must never claim Real-User
Monitoring or "real user" telemetry. Synthetic lab measurements are a
proxy for release confidence — calling them RUM would mislead users.

This test has two parts:

1. **Required-phrase coverage** — every Finding emitted by the
 performance module begins with the prefix "Synthetic performance
 check". We verify this by importing the findings module and checking
 the constant the translator pulls in.
2. **Forbidden-phrase audit** — we grep the performance Python package
 and the TS perf helper package for the literal claim that the module
 reports "Real User Monitoring" / "real-user telemetry" / etc. as
 product output. The phrase "Real-User Monitoring" appears in the
 findings text to *deny* that interpretation; the guard exempts that
 exact phrasing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.performance.findings import _LABEL

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PREFIX = "Synthetic performance check"

# Phrases the module must never USE to describe what it measures. The
# negation phrasing "not Real-User Monitoring" is fine — that's how the
# findings text actively warns the reader. We grep for stronger claims.
FORBIDDEN_PHRASES = (
    "Real-User Monitoring data captured",
    "RUM data captured",
    "field telemetry captured",
    "production user telemetry",
)

SCAN_TARGETS = (
    REPO_ROOT / "modules" / "performance",
    REPO_ROOT / "packages" / "ts-runtime" / "src" / "perf",
)


def test_required_prefix_constant_is_correct() -> None:
    assert _LABEL == REQUIRED_PREFIX


@pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
def test_module_outputs_never_claim_rum(phrase: str) -> None:
    hits: list[str] = []
    for root in SCAN_TARGETS:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in {".py", ".ts", ".json", ".md"}:
                continue
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            text = p.read_text(encoding="utf-8")
            if phrase in text:
                hits.append(f"{p.relative_to(REPO_ROOT)}: contains forbidden phrase {phrase!r}")
    assert hits == [], "\n".join(hits)
