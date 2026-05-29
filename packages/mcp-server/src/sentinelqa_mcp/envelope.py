"""Agent envelope (ADR-0023 §AgentEnvelope, task 18.03).

Every tool — success or failure — returns the same shape. The envelope
sits *inside* the MCP ``tools/call`` response, in the ``text`` block of
the single ``content`` item. The MCP spec ships ``text``, ``image``, and
``resource`` content kinds — not free-form JSON — so we encode the
envelope as deterministic JSON inside a text block.

The shape is locked by the Draft 2020-12 schema at
``packages/shared-schema/agent-envelope.schema.json``.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Bump this when the envelope shape changes — same deprecation policy as
# the SDK (ADR-0021).
AGENT_ENVELOPE_SCHEMA_VERSION: str = "1"


class AgentEnvelope(BaseModel):
    """Canonical wrapper for every MCP tool response.

    - ``schema_version`` — pinned to :data:`AGENT_ENVELOPE_SCHEMA_VERSION`.
    - ``tool`` — fully qualified tool name (e.g. ``"sentinel.audit"``).
    - ``result`` — tool-specific payload. ``None`` ONLY when ``errors``
      is non-empty (an error envelope carries no result).
    - ``errors`` — list of redacted error agent-messages
      (``SentinelError.to_agent_message()`` shape). Empty on success.
    - ``evidence_refs`` — relative paths beneath the run directory the
      caller can fetch with ``sentinel.read_report``. Empty when the
      tool produced no on-disk evidence.
    """

    SCHEMA_VERSION: ClassVar[str] = AGENT_ENVELOPE_SCHEMA_VERSION

    schema_version: str = Field(default=AGENT_ENVELOPE_SCHEMA_VERSION)
    tool: str = Field(pattern=r"^sentinel\.[a-z_]+$")
    result: dict[str, Any] | list[Any] | None = None
    errors: tuple[dict[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _result_xor_errors(self) -> AgentEnvelope:
        if self.result is None and not self.errors:
            raise ValueError(
                "AgentEnvelope requires either a non-None `result` or "
                "at least one entry in `errors`."
            )
        if self.result is not None and self.errors:
            # Both is OK: a partial result with a non-fatal warning. But
            # we require the schema version to be set so the consumer
            # can route on it.
            pass
        return self

    @property
    def is_error(self) -> bool:
        return self.result is None and bool(self.errors)

    def to_wire(self) -> str:
        """Render the envelope as deterministic JSON (sorted keys, no ASCII escapes)."""

        payload = self.model_dump(mode="json", exclude_none=False)
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def success(
    tool: str,
    result: dict[str, Any] | list[Any],
    *,
    evidence_refs: tuple[str, ...] = (),
) -> AgentEnvelope:
    """Build a success envelope for ``tool`` with ``result``."""

    return AgentEnvelope(
        tool=tool,
        result=result,
        errors=(),
        evidence_refs=evidence_refs,
    )


def failure(
    tool: str,
    error_message: dict[str, Any],
    *,
    evidence_refs: tuple[str, ...] = (),
) -> AgentEnvelope:
    """Build an error envelope for ``tool`` carrying a single error message."""

    return AgentEnvelope(
        tool=tool,
        result=None,
        errors=(error_message,),
        evidence_refs=evidence_refs,
    )


__all__ = [
    "AGENT_ENVELOPE_SCHEMA_VERSION",
    "AgentEnvelope",
    "failure",
    "success",
]
