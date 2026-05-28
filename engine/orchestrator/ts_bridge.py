"""Python ↔ TypeScript JSONL parser (CLAUDE.md §8, ADR-0009).

The TS runtime (`@sentinelqa/ts-runtime`) emits one JSON event per
stdout line. This module:

  - Defines a typed Pydantic model per event kind (discriminated by
    ``type``).
  - Parses a single line via :func:`parse_event`.
  - Streams events from an asyncio :class:`StreamReader` via
    :func:`stream_events`, raising :class:`ProtocolParseError` on
    malformed lines.

The wire format is locked by
``packages/shared-schema/ts-events.schema.json``. Both halves of the
bridge are kept in sync by the cross-language parity test
(``tests/integration/protocol/test_parity.py``).

This module deliberately does *not* import Playwright. Phase 04 owns
only the message shape; the runner (Phase 08) is responsible for
spawning the TS process and feeding stdout into :func:`stream_events`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROTOCOL_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProtocolParseError(ValueError):
    """Raised when a JSONL line cannot be parsed as a TS event.

    Carries the offending ``line`` and an optional ``cause`` so callers
    can surface the original validation error without re-parsing.
    """

    def __init__(self, message: str, *, line: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.cause = cause


# ---------------------------------------------------------------------------
# Base envelope
# ---------------------------------------------------------------------------


class _EventBase(BaseModel):
    """Common envelope every event carries.

    The bridge is permissive about ``extra``: TS adds new optional
    fields between schema bumps (additive only) and Python should not
    fail to parse old streams. Drift in the *required* fields is what
    we want to detect.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: str
    seq: int = Field(ge=1)
    ts: datetime


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------


class SerializedError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    message: str
    stack: str | None = None


# ---------------------------------------------------------------------------
# Event models — one per TsEvent discriminator
# ---------------------------------------------------------------------------


class RunStartEvent(_EventBase):
    type: Literal["run.start"]
    run_id: str = Field(min_length=1)
    target: str = Field(min_length=1)
    started_at: datetime


class RunEndEvent(_EventBase):
    type: Literal["run.end"]
    run_id: str = Field(min_length=1)
    finished_at: datetime
    status: Literal["passed", "failed", "timed_out", "interrupted", "errored"]
    tests_total: int = Field(ge=0)
    tests_failed: int = Field(ge=0)


class TestStartEvent(_EventBase):
    type: Literal["test.start"]
    test_id: str = Field(min_length=1)
    title: str
    file: str


class TestEndEvent(_EventBase):
    type: Literal["test.end"]
    test_id: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    status: Literal["passed", "failed", "timed_out", "skipped"]
    retries: int = Field(ge=0)
    error: SerializedError | None = None


class StepStartEvent(_EventBase):
    type: Literal["step.start"]
    test_id: str | None = None
    step_id: str = Field(min_length=1)
    name: str


class StepEndEvent(_EventBase):
    type: Literal["step.end"]
    test_id: str | None = None
    step_id: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    ok: bool
    error: SerializedError | None = None


class EvidenceEvent(_EventBase):
    type: Literal["evidence"]
    test_id: str | None = None
    step_id: str | None = None
    evidence_kind: Literal[
        "trace",
        "screenshot",
        "video",
        "har",
        "dom_snapshot",
        "network_log",
        "console_log",
    ]
    path: str = Field(min_length=1)
    label: str


class NetworkRequestEvent(_EventBase):
    type: Literal["network.request"]
    test_id: str | None = None
    request_id: str = Field(min_length=1)
    url: str
    method: str
    content_length: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class NetworkResponseEvent(_EventBase):
    type: Literal["network.response"]
    test_id: str | None = None
    request_id: str = Field(min_length=1)
    url: str
    status: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    content_length: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class ConsoleEvent(_EventBase):
    type: Literal["console"]
    test_id: str | None = None
    level: Literal["log", "debug", "info", "warn", "error"]
    message: str
    source: str


class DomSnapshotEvent(_EventBase):
    type: Literal["dom.snapshot"]
    test_id: str | None = None
    step_id: str | None = None
    path: str
    label: str


class ModuleEventEvent(_EventBase):
    type: Literal["module.event"]
    module: str
    name: str
    payload: dict[str, Any]


class LogEvent(_EventBase):
    type: Literal["log"]
    level: Literal["debug", "info", "warn", "error"]
    msg: str
    fields: dict[str, Any]


class ErrorEvent(_EventBase):
    type: Literal["error"]
    code: str = Field(min_length=1)
    message: str
    stack: str | None = None


TsEvent = Annotated[
    RunStartEvent
    | RunEndEvent
    | TestStartEvent
    | TestEndEvent
    | StepStartEvent
    | StepEndEvent
    | EvidenceEvent
    | NetworkRequestEvent
    | NetworkResponseEvent
    | ConsoleEvent
    | DomSnapshotEvent
    | ModuleEventEvent
    | LogEvent
    | ErrorEvent,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


_EVENT_REGISTRY: dict[str, type[_EventBase]] = {
    "run.start": RunStartEvent,
    "run.end": RunEndEvent,
    "test.start": TestStartEvent,
    "test.end": TestEndEvent,
    "step.start": StepStartEvent,
    "step.end": StepEndEvent,
    "evidence": EvidenceEvent,
    "network.request": NetworkRequestEvent,
    "network.response": NetworkResponseEvent,
    "console": ConsoleEvent,
    "dom.snapshot": DomSnapshotEvent,
    "module.event": ModuleEventEvent,
    "log": LogEvent,
    "error": ErrorEvent,
}


def parse_event(line: str) -> _EventBase:
    """Parse a single JSONL line into the matching typed event."""

    stripped = line.rstrip("\r\n")
    if not stripped:
        raise ProtocolParseError("empty event line", line=line)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ProtocolParseError(f"invalid JSON: {exc}", line=line, cause=exc) from exc
    if not isinstance(payload, dict):
        raise ProtocolParseError(
            f"event must be a JSON object (got {type(payload).__name__})",
            line=line,
        )
    type_field = payload.get("type")
    if not isinstance(type_field, str):
        raise ProtocolParseError("event missing string `type` field", line=line)
    model = _EVENT_REGISTRY.get(type_field)
    if model is None:
        raise ProtocolParseError(f"unknown event type: {type_field!r}", line=line)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolParseError(
            f"event failed schema validation: {exc.error_count()} errors",
            line=line,
            cause=exc,
        ) from exc


def parse_events(lines: Iterable[str]) -> list[_EventBase]:
    """Convenience wrapper that parses a sequence of lines eagerly."""

    return [parse_event(line) for line in lines if line.strip()]


async def stream_events(reader: Any) -> AsyncIterator[_EventBase]:
    """Yield typed events from an async-iterable line source.

    ``reader`` must be an asynchronous iterator yielding ``bytes`` or
    ``str`` lines — typically an :class:`asyncio.StreamReader` (we read
    ``bytes`` and decode UTF-8). The runner (Phase 08) is responsible
    for spawning the TS process; this function only consumes its
    stdout. Empty lines (heartbeats) are silently skipped.
    """

    async for raw in reader:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        elif isinstance(raw, str):
            text = raw
        else:  # pragma: no cover — defensive
            raise ProtocolParseError(
                f"unsupported reader item: {type(raw).__name__}",
                line=str(raw),
            )
        if not text.strip():
            continue
        yield parse_event(text)


__all__ = [
    "PROTOCOL_VERSION",
    "ProtocolParseError",
    "SerializedError",
    "TsEvent",
    "RunStartEvent",
    "RunEndEvent",
    "TestStartEvent",
    "TestEndEvent",
    "StepStartEvent",
    "StepEndEvent",
    "EvidenceEvent",
    "NetworkRequestEvent",
    "NetworkResponseEvent",
    "ConsoleEvent",
    "DomSnapshotEvent",
    "ModuleEventEvent",
    "LogEvent",
    "ErrorEvent",
    "parse_event",
    "parse_events",
    "stream_events",
]
