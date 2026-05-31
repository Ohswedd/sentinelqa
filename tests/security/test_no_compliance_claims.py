"""CLAUDE §28 + Phase 34 wording rule: compliance outputs never claim
the target is *compliant*. Allowed: "Automated <regime> check found",
"Automated <regime> check passed", "manual review recommended".
Forbidden in product outputs: "fully WCAG/GDPR/CCPA/SOC 2 compliant",
"WCAG/GDPR/CCPA/SOC 2 compliant", "we are compliant".

The guard greps every file under ``modules/compliance/``,
``policy/compliance/``, and ``engine/policy/compliance.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_PHRASES = (
    "fully WCAG compliant",
    "fully GDPR compliant",
    "fully CCPA compliant",
    "fully SOC 2 compliant",
    "you are GDPR compliant",
    "your site is GDPR compliant",
    "you are CCPA compliant",
    "we are GDPR compliant",
    "we are CCPA compliant",
    "we are SOC 2 compliant",
    "we are SOC2 compliant",
    "WCAG compliant",
    "GDPR compliant",
    "CCPA compliant",
)

SCAN_TARGETS = (
    REPO_ROOT / "modules" / "compliance",
    REPO_ROOT / "policy" / "compliance",
    REPO_ROOT / "engine" / "policy" / "compliance.py",
)


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for root in SCAN_TARGETS:
        if root.is_file():
            out.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".yaml", ".yml", ".md", ".json"}:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            out.append(path)
    return out


@pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
def test_compliance_outputs_never_contain_forbidden_phrase(phrase: str) -> None:
    hits: list[str] = []
    for path in _iter_files():
        text = path.read_text(encoding="utf-8")
        if phrase in text:
            hits.append(f"{path.relative_to(REPO_ROOT)}: contains forbidden phrase " f"{phrase!r}")
    assert hits == [], "\n".join(hits)
