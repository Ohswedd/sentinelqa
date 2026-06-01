"""LLM-PLACEHOLDER-TEXT — "coming soon" placeholders in flows.

Pure function over :class:`RenderedTextSample` records. The severity
matrix from the task file:

* on a P0 flow → high
* on an authenticated flow → medium
* otherwise → low

We match a small set of high-precision placeholder strings so we
don't catch unrelated marketing copy.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from engine.domain.finding import Severity

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import RenderedTextSample
from modules.llm_audit.rules import LLM_PLACEHOLDER_TEXT

_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("coming_soon", re.compile(r"\bcoming\s+soon\b", re.IGNORECASE)),
    ("tbd", re.compile(r"\bTBD\b")),
    ("todo", re.compile(r"\bTODO[:\s]")),
    ("lorem", re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE)),
    (
        "not_implemented",
        re.compile(r"\b(?:feature|function)\s+not\s+implemented\b", re.IGNORECASE),
    ),
    ("placeholder_word", re.compile(r"\bplaceholder\b", re.IGNORECASE)),
    ("templated", re.compile(r"\{\{?\s*placeholder\s*\}?\}")),
)


def check_coming_soon(samples: Iterable[RenderedTextSample]) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for sample in samples:
        for kind, pattern in _PLACEHOLDER_PATTERNS:
            match = pattern.search(sample.text)
            if not match:
                continue
            severity = _severity_for(sample)
            findings.append(
                CheckFinding(
                    rule_id=LLM_PLACEHOLDER_TEXT.id,
                    title=f"Placeholder text on {sample.route_url}",
                    description=(
                        f"The route {sample.route_url} renders placeholder "
                        f"text matching the {kind!r} indicator. Replace it "
                        "with real copy or hide the screen until it ships."
                    ),
                    route=sample.route_url,
                    selector=sample.selector,
                    severity_override=severity,
                    snippet=_extract_line_window(sample.text, match.start(), match.end()),
                    extra_context=(
                        ("indicator", kind),
                        ("priority", sample.priority),
                        (
                            "authenticated_flow",
                            str(sample.is_authenticated_flow).lower(),
                        ),
                    ),
                )
            )
            break  # one finding per sample (first-match wins)
    return tuple(findings)


def _severity_for(sample: RenderedTextSample) -> Severity:
    if sample.priority == "p0":
        return "high"
    if sample.is_authenticated_flow or sample.priority == "p1":
        return "medium"
    return "low"


def _extract_line_window(body: str, start: int, end: int) -> str:
    line_start = body.rfind("\n", 0, start) + 1
    line_end = body.find("\n", end)
    if line_end == -1:
        line_end = len(body)
    line = body[line_start:line_end].strip()
    if len(line) > 240:
        line = line[:240] + "…"
    return line


__all__ = ["check_coming_soon"]
