"""LLM redaction policy (, ADR-0042).

Every outgoing request and incoming response passes through
:func:`engine.policy.redaction.redact` before being logged. The wrapper
here applies a couple of LLM-specific rules:

- The literal API key value (read from the env var) is NEVER substituted
 into any log line — providers MUST pass the key through ``auth_headers``
 on the wire only.
- Prompt text is excluded from audit log entries entirely. The audit log
 is for safety / accountability, not for prompt debugging; debug-mode
 logging (off by default) is the place to surface prompts.
- Response text is excluded from audit log entries for the same reason.
 The ``usage`` block (token counts + cost) is what flows to the log.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from engine.policy.redaction import redact, redact_headers


@dataclass(frozen=True, slots=True)
class LlmRedactionPolicy:
    """Per-provider redaction toggles.

    Defaults are tuned for production: NO prompts in audit logs, NO
    response text in audit logs, headers redacted via the canonical
    rule set. Tests opt into ``include_prompts=True`` only with
    explicit fixtures.
    """

    include_prompts_in_audit: bool = False
    include_response_text_in_audit: bool = False


def redact_request(
    payload: Mapping[str, Any],
    *,
    policy: LlmRedactionPolicy | None = None,
) -> dict[str, Any]:
    """Redact an outbound request payload for audit logging.

    The provider's HTTP body is NOT logged verbatim — only a structural
    summary survives. Specifically:

    - ``messages`` / ``contents`` arrays are collapsed to a count.
    - ``system`` / ``prompt`` string fields are replaced with a hash hint.
    - Every other key flows through the standard redactor.
    """

    policy = policy or LlmRedactionPolicy()
    summary: dict[str, Any] = {}
    for key, value in payload.items():
        if (
            key in {"messages", "contents", "input", "prompt"}
            and not policy.include_prompts_in_audit
        ):
            if isinstance(value, list):
                summary[key] = {"count": len(value), "redacted": True}
            elif isinstance(value, str):
                summary[key] = {"chars": len(value), "redacted": True}
            else:
                summary[key] = {"redacted": True}
            continue
        if key in {"system", "instruction"} and not policy.include_prompts_in_audit:
            summary[key] = {"chars": len(str(value)), "redacted": True}
            continue
        if key in {"response_schema", "responseSchema", "json_schema"}:
            # Schemas are not secrets but they are bulky — log only that
            # structured output was requested.
            summary[key] = {"structured_output": True}
            continue
        summary[key] = value
    redacted = redact(summary)
    assert isinstance(redacted, dict)
    return redacted


def redact_response(
    payload: Mapping[str, Any],
    *,
    policy: LlmRedactionPolicy | None = None,
) -> dict[str, Any]:
    """Redact a response body for audit logging.

    Keeps ``usage``, ``model``, ``id`` / ``response_id`` and similar
    accounting fields. Drops the model output text by default.
    """

    policy = policy or LlmRedactionPolicy()
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"choices", "candidates", "message", "content", "output_text"}:
            if policy.include_response_text_in_audit:
                safe[key] = value
            else:
                safe[key] = {"redacted": True}
            continue
        safe[key] = value
    redacted = redact(safe)
    assert isinstance(redacted, dict)
    return redacted


def redact_auth_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Apply the canonical header redactor (re-exported for callers)."""

    return redact_headers(headers)


__all__ = [
    "LlmRedactionPolicy",
    "redact_auth_headers",
    "redact_request",
    "redact_response",
]
