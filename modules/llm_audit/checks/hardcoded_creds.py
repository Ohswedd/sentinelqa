"""LLM-HARDCODED-CRED — hardcoded credentials in shipped source (task 19.08).

Pattern-matches a small set of high-precision hardcoded-credential
shapes against :class:`SourceFile` bodies:

* obvious literal pairs (``username: 'admin'`` next to a password line),
* JWT / bearer tokens embedded in JS strings,
* connection strings (``postgres://`` / ``mysql://``) with embedded
  credentials,
* env values masquerading as constants (``API_KEY = "sk-..."``).

Per CLAUDE.md §33, every emitted finding routes its observed snippet
through :func:`engine.policy.redaction.redact` so the secret value is
never persisted unmasked.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from engine.policy.redaction import redact

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import SourceFile
from modules.llm_audit.rules import LLM_HARDCODED_CRED

# Each pattern captures `(kind, regex, hint)`. Patterns are ordered most
# specific → least specific so a single line only triggers once.
_CRED_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "jwt_literal",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "Source file embeds a literal JWT.",
    ),
    (
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "Source file embeds an OpenAI-style API key.",
    ),
    (
        "stripe_secret",
        re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
        "Source file embeds a Stripe-style secret key.",
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "Source file embeds an AWS access key ID.",
    ),
    (
        "db_connection_string",
        re.compile(
            r"\b(?:postgres|postgresql|mysql|mongodb)(?:\+srv)?://[^:\s]+:[^@\s]+@[^/\s]+",
            re.IGNORECASE,
        ),
        "Source file embeds a database connection string with credentials.",
    ),
    (
        "demo_admin_pair",
        re.compile(
            r"(?:username|email)\s*[:=]\s*['\"](?:admin|root|demo|test)@?[^'\"]*['\"][\s,;]*(?:[\r\n]+\s*\w*\s*[:=]\s*)?(?:password|pass|pwd)\s*[:=]\s*['\"][^'\"]{4,64}['\"]",
            re.IGNORECASE,
        ),
        "Source file pairs a demo username with a hardcoded password.",
    ),
    (
        "password_constant",
        re.compile(
            r"\b(?:const|let|var|final)\s+(?:DEFAULT|DEMO|ADMIN|TEST)_?PASS(?:WORD)?\s*=\s*['\"][^'\"]{4,64}['\"]",
            re.IGNORECASE,
        ),
        "Source file hardcodes a demo / admin password constant.",
    ),
    (
        "auth_token_assignment",
        re.compile(
            r"\b(?:auth|api|access|secret|bearer)[_-]?(?:token|key)\s*[:=]\s*['\"][A-Za-z0-9\-_]{16,}['\"]",
            re.IGNORECASE,
        ),
        "Source file hardcodes an auth / API token literal.",
    ),
)


_REDACTED_MARKER = "[REDACTED:hardcoded_credential]"


def check_hardcoded_credentials(
    source_files: Iterable[SourceFile],
) -> tuple[CheckFinding, ...]:
    """Return one CheckFinding per (file, indicator) match.

    The snippet is double-redacted before it leaves this function:

    1. The exact matched substring (the credential value) is replaced
       with ``[REDACTED:hardcoded_credential]`` so the literal never
       appears verbatim.
    2. The resulting line passes through
       :func:`engine.policy.redaction.redact` to catch any nearby
       known-format token (JWT, AWS key, etc.) the first pass missed.
    """

    findings: list[CheckFinding] = []
    for source in source_files:
        for kind, pattern, hint in _CRED_PATTERNS:
            for match in pattern.finditer(source.body):
                line = source.body.count("\n", 0, match.start()) + 1
                snippet = _extract_line_window_redacted(source.body, match.start(), match.end())
                redacted_snippet = redact(snippet)
                if not isinstance(redacted_snippet, str):
                    redacted_snippet = str(redacted_snippet)
                findings.append(
                    CheckFinding(
                        rule_id=LLM_HARDCODED_CRED.id,
                        title=f"{source.path} contains a hardcoded credential",
                        description=hint,
                        file=source.path,
                        line=line,
                        snippet=redacted_snippet,
                        extra_context=(("indicator", kind),),
                    )
                )
    return tuple(findings)


def _extract_line_window_redacted(body: str, start: int, end: int) -> str:
    """Return the matched-line window with the matched span redacted.

    The match itself is replaced with a literal ``[REDACTED:...]``
    marker so the credential value cannot survive in the snippet, even
    if no downstream redaction rule fires.
    """

    line_start = body.rfind("\n", 0, start) + 1
    line_end = body.find("\n", end)
    if line_end == -1:
        line_end = len(body)
    prefix = body[line_start:start]
    suffix = body[end:line_end]
    line = (prefix + _REDACTED_MARKER + suffix).strip()
    if len(line) > 240:
        line = line[:240] + "…"
    return line


__all__ = ["check_hardcoded_credentials"]
