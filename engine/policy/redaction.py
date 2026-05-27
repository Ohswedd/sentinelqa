"""Redaction primitives for SentinelQA.

Stub. The full implementation (regex + key-based redaction over strings,
dicts, lists, and the structured logging context) lands in Phase 01
(`plans/phase-01-core-domain-config/05-redaction.md`).

Per CLAUDE.md §37 ("no fake completion"), this is one of two allowed
`NotImplementedError`s in Phase 00: importable so other phases can wire it
in, but explicitly fails when called so no caller mistakes the stub for a
real redactor.
"""

from __future__ import annotations

RedactionInput = str | dict[str, object] | list[object]


def redact(value: RedactionInput) -> RedactionInput:
    """Redact sensitive substrings or keys from ``value``.

    Phase 01 will implement: regex-based masking for tokens/keys/cookies,
    key-name-based masking for dicts (e.g. ``authorization``, ``cookie``,
    ``api_key``), and recursive descent into lists/dicts. Until then this
    function raises ``NotImplementedError`` so accidental callers cannot
    silently leak data.
    """
    raise NotImplementedError(
        "engine.policy.redaction.redact is a Phase-00 stub; real implementation "
        "lands in Phase 01 (plans/phase-01-core-domain-config/05-redaction.md)."
    )
