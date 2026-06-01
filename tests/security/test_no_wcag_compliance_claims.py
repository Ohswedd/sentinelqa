"""CLAUDE §28 guard: the accessibility module must never claim "fully WCAG
compliant" / "WCAG compliant" in its outputs.

The guard greps every file under ``modules/accessibility/`` and
``packages/ts-runtime/src/a11y/``. The our product spec4 section is allowed to
**discuss** the forbidden phrasing for documentation purposes; this
guard targets product output only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_PHRASES = (
    "fully WCAG compliant",
    "fully wcag compliant",
    "WCAG compliant",
    "wcag compliant",
)

SCAN_TARGETS = (
    REPO_ROOT / "modules" / "accessibility",
    REPO_ROOT / "packages" / "ts-runtime" / "src" / "a11y",
)


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for root in SCAN_TARGETS:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in {".py", ".ts", ".json", ".md"}:
                continue
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            out.append(p)
    return out


@pytest.mark.parametrize("phrase", FORBIDDEN_PHRASES)
def test_module_outputs_never_contain_forbidden_phrase(phrase: str) -> None:
    hits: list[str] = []
    for path in _iter_files():
        text = path.read_text(encoding="utf-8")
        if phrase in text:
            hits.append(f"{path.relative_to(REPO_ROOT)}: contains forbidden phrase {phrase!r}")
    assert hits == [], "\n".join(hits)
