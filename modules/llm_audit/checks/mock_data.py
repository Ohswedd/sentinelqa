"""LLM-MOCK-DATA-SHIPPED — mock fixtures shipped to production.

Two complementary signals:

1. JS bundles / source files contain mock indicators — explicit names
 (``mockData``, ``__MOCK__``), faker / placeholder values
 (``lorem ipsum``, ``John Doe``, ``jane@example.com``), or hardcoded
 imports of mock JSON files.
2. Rendered text on a route contains the same placeholder values.

The check returns one finding per (file, indicator) so the report can
list every leak.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from engine.domain.finding import Severity

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import BundleSnippet, RenderedTextSample
from modules.llm_audit.rules import LLM_MOCK_DATA_SHIPPED

# Patterns ordered most-specific-first so the first match wins.
_MOCK_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "mock_export",
        re.compile(
            r"\b(?:export\s+(?:const|let|var)\s+)?(?:__MOCK__|mockData|MOCK_DATA|fakeData)\b"
        ),
        "Identifier suggests mock data is exported / referenced.",
    ),
    (
        "mock_import",
        re.compile(r"""import\s+[^;\n]*?from\s+['"]([^'"]*?(?:mock|fixture)s?\.json)['"]"""),
        "Source imports a mock JSON file directly.",
    ),
    (
        "lorem_ipsum",
        re.compile(r"lorem\s+ipsum", re.IGNORECASE),
        "Placeholder filler text (lorem ipsum).",
    ),
    (
        "placeholder_user",
        re.compile(r"\b(?:John\s+Doe|Jane\s+Doe|Test\s+User)\b"),
        "Placeholder user name (John Doe / Jane Doe / Test User).",
    ),
    (
        "placeholder_email",
        re.compile(
            r"\b[a-z0-9._%+-]+@(?:example|test|mock|placeholder)\.[a-z]{2,8}\b",
            re.IGNORECASE,
        ),
        "Placeholder email address.",
    ),
    (
        "todo_user_data",
        re.compile(
            r"\b(?:TODO[:\s]+(?:add|replace)\s+(?:real|production)\s+data|FIXME[:\s]+real\s+data)\b",
            re.IGNORECASE,
        ),
        "Author TODO admits the data is not real.",
    ),
)


def check_mock_data_in_bundles(
    bundles: Iterable[BundleSnippet],
) -> tuple[CheckFinding, ...]:
    """Flag mock-data indicators in source / JS-bundle bodies."""

    findings: list[CheckFinding] = []
    for snippet in bundles:
        for kind, pattern, hint in _MOCK_PATTERNS:
            match = pattern.search(snippet.body)
            if not match:
                continue
            # Record line number (1-based) of the first match.
            line = snippet.body.count("\n", 0, match.start()) + 1
            findings.append(
                CheckFinding(
                    rule_id=LLM_MOCK_DATA_SHIPPED.id,
                    title=f"{snippet.path} ships mock data",
                    description=hint,
                    file=snippet.path,
                    line=line,
                    snippet=_extract_line_window(snippet.body, match.start(), match.end()),
                    extra_context=(("indicator", kind),),
                )
            )
    return tuple(findings)


def check_mock_data_in_rendered_text(
    samples: Iterable[RenderedTextSample],
) -> tuple[CheckFinding, ...]:
    """Flag rendered text on a real route that contains placeholder content."""

    findings: list[CheckFinding] = []
    for sample in samples:
        for kind, pattern, hint in _MOCK_PATTERNS:
            match = pattern.search(sample.text)
            if not match:
                continue
            severity: Severity = "high" if sample.is_authenticated_flow else "medium"
            findings.append(
                CheckFinding(
                    rule_id=LLM_MOCK_DATA_SHIPPED.id,
                    title=f"Rendered text on {sample.route_url} matches mock pattern",
                    description=hint,
                    route=sample.route_url,
                    selector=sample.selector,
                    severity_override=severity,
                    snippet=_extract_line_window(sample.text, match.start(), match.end()),
                    extra_context=(
                        ("indicator", kind),
                        ("authenticated_flow", str(sample.is_authenticated_flow).lower()),
                    ),
                )
            )
    return tuple(findings)


def _extract_line_window(body: str, start: int, end: int) -> str:
    """Return the line containing ``[start:end]`` clipped to 240 chars."""

    line_start = body.rfind("\n", 0, start) + 1
    line_end = body.find("\n", end)
    if line_end == -1:
        line_end = len(body)
    line = body[line_start:line_end].strip()
    if len(line) > 240:
        line = line[:240] + "…"
    return line


__all__ = [
    "check_mock_data_in_bundles",
    "check_mock_data_in_rendered_text",
]
