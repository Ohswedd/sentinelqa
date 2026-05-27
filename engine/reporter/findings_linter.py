"""Vague-finding linter (task 03.02).

CLAUDE.md §24 forbids vague findings ("Security issue found." is the
canonical bad example). The linter emits non-fatal warnings so reviewers
and Phase 24 plugin contract tests can flag drift. Callers decide whether
to surface warnings to the user or include them in CI output.

The linter is intentionally lenient: it flags obvious anti-patterns
(too-short titles, banned phrases, empty descriptions) without inventing
quality thresholds the PRD has not committed to.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from engine.domain.finding import Finding

# Minimum title length. CLAUDE.md §24 specifies < 8 chars is too short.
MIN_TITLE_LENGTH: int = 8

# Maximum description "specificity ratio" cutoff. A description is too
# vague if it consists entirely of banned generic words and lacks any
# concrete locator, file, route, or evidence reference. We model this as
# "contains a banned phrase AND lacks any specifics."
BANNED_DESCRIPTION_PHRASES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bissue\s+found\b", re.IGNORECASE),
    re.compile(r"\berror\s+found\b", re.IGNORECASE),
    re.compile(r"\bproblem\s+found\b", re.IGNORECASE),
    re.compile(r"\bsomething\s+(?:is\s+)?wrong\b", re.IGNORECASE),
    re.compile(r"\bgeneric\s+error\b", re.IGNORECASE),
)

# A description that mentions at least one of these is considered to have
# concrete specifics. (Approximate — Phase 19's LLM-audit module may
# refine the heuristic; the goal here is to catch the worst offenders.)
SPECIFICITY_HINTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/[a-zA-Z0-9_\-/.]+"),  # a path-like token
    re.compile(
        r"[A-Za-z0-9_.-]+\.(?:py|ts|tsx|js|jsx|html|css|json|yaml|yml|sql|sh|go|rs|rb|java|kt|swift)\b"
    ),
    re.compile(r"\b\d{2,5}\s*(?:ms|s|kb|mb|bytes|chars)\b", re.IGNORECASE),
    re.compile(r"(?:HTTP|status)\s+\d{3}", re.IGNORECASE),
    re.compile(
        r"\b(?:set-cookie|authorization|content-security-policy|x-frame-options)\b", re.IGNORECASE
    ),
)


@dataclass(frozen=True, slots=True)
class FindingsLinterWarning:
    """One linter complaint about a finding."""

    finding_id: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"finding_id": self.finding_id, "code": self.code, "message": self.message}


def lint_finding(finding: Finding) -> list[FindingsLinterWarning]:
    """Return all linter warnings for a single finding."""

    warnings: list[FindingsLinterWarning] = []

    title = finding.title.strip()
    if len(title) < MIN_TITLE_LENGTH:
        warnings.append(
            FindingsLinterWarning(
                finding_id=finding.id,
                code="L-FND-001",
                message=(
                    f"Title is too short ({len(title)} chars; minimum {MIN_TITLE_LENGTH}). "
                    "CLAUDE.md §24: findings must be specific."
                ),
            )
        )

    description = finding.description.strip()
    banned_hit = next(
        (p for p in BANNED_DESCRIPTION_PHRASES if p.search(description)),
        None,
    )
    has_specifics = any(p.search(description) for p in SPECIFICITY_HINTS)

    if banned_hit is not None and not has_specifics:
        warnings.append(
            FindingsLinterWarning(
                finding_id=finding.id,
                code="L-FND-002",
                message=(
                    f"Description matches vague phrase {banned_hit.pattern!r} and lacks "
                    "concrete specifics (path, file, status code, header, or measurement). "
                    'Reword like "Session cookie on /login is missing HttpOnly and Secure flags."'
                ),
            )
        )

    if not description:
        warnings.append(
            FindingsLinterWarning(
                finding_id=finding.id,
                code="L-FND-003",
                message="Description is empty; CLAUDE.md §24 requires evidence-backed prose.",
            )
        )

    if finding.severity in {"critical", "high", "medium"} and not finding.evidence:
        warnings.append(
            FindingsLinterWarning(
                finding_id=finding.id,
                code="L-FND-004",
                message=(
                    f"Severity {finding.severity!r} requires at least one evidence artifact "
                    "(PRD §20 — every failure must have evidence)."
                ),
            )
        )

    return warnings


def lint_findings(findings: Iterable[Finding]) -> list[FindingsLinterWarning]:
    """Return concatenated linter warnings for a collection of findings."""

    out: list[FindingsLinterWarning] = []
    for f in findings:
        out.extend(lint_finding(f))
    return out


def first_blocking_warning(
    findings: Sequence[Finding],
) -> FindingsLinterWarning | None:
    """Return the first warning whose code blocks the writer.

    Phase 03 promotes the evidence-required rule (``L-FND-004``) to a
    *blocking* warning. Other codes are advisory.
    """

    for f in findings:
        for w in lint_finding(f):
            if w.code == "L-FND-004":
                return w
    return None


__all__ = [
    "BANNED_DESCRIPTION_PHRASES",
    "FindingsLinterWarning",
    "MIN_TITLE_LENGTH",
    "SPECIFICITY_HINTS",
    "first_blocking_warning",
    "lint_finding",
    "lint_findings",
]
