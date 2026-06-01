"""Agent-message helpers (the documentation, our engineering rules).

A thin formatting layer over the dicts produced by
:meth:`AuditResult.to_agent_messages`,
:meth:`engine.domain.Finding.to_agent_message`,
:meth:`engine.domain.RepairSuggestion.to_agent_message`, and
:meth:`engine.errors.SentinelError.to_agent_message`.

The helpers do NOT generate text — they serialise already-built
dictionaries. That keeps the wire format deterministic and lets agents
re-parse on the other side.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from sentinelqa._agent_messages import (
    AGENT_MESSAGE_SCHEMA_VERSION,
    audit_result_to_agent_messages,
    finding_to_agent_message,
    repair_suggestion_to_agent_message,
)

Format = Literal["ndjson", "jsonl", "list"]


def format(
    messages: Iterable[Mapping[str, Any]],
    *,
    format: Format = "ndjson",
) -> str:
    """Serialise an iterable of agent messages.

    ``format``:

    - ``"ndjson"`` / ``"jsonl"`` — newline-delimited JSON (one message per
    line, no trailing newline; identical output for both).
    - ``"list"`` — a single JSON array of all messages.

    Output is deterministic: keys sorted, no ASCII escaping. Suitable for
    piping straight into an LLM context window or into a file-based
    evidence trail.
    """

    if format == "ndjson" or format == "jsonl":
        return "\n".join(json.dumps(dict(m), sort_keys=True, ensure_ascii=False) for m in messages)
    if format == "list":
        return json.dumps(
            [dict(m) for m in messages],
            sort_keys=True,
            ensure_ascii=False,
        )
    raise ValueError(f"unknown format {format!r} — expected 'ndjson', 'jsonl', or 'list'")


__all__ = [
    "AGENT_MESSAGE_SCHEMA_VERSION",
    "Format",
    "audit_result_to_agent_messages",
    "finding_to_agent_message",
    "format",
    "repair_suggestion_to_agent_message",
]
