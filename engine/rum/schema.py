# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""RUM JSONL event schema.

Mirrors the public envelope used by the synthetic runner
(``packages/ts-runtime/src/protocol.ts``): every event carries
``schema_version`` + ``type`` + ``seq`` + ``ts`` and a typed payload.
For the v1.9.0 MVP we accept a focused subset of events that map to
real-user activity:

* ``run.start`` / ``run.end``       — RUM session bounds.
* ``page.view``                     — a route the user visited.
* ``page.error``                    — an uncaught JS error.
* ``network.request`` /
  ``network.response`` /
  ``network.failure``               — XHR / fetch lifecycle.
* ``console``                       — console messages (kind filtered
                                       to ``error`` / ``warn`` by
                                       default on the SDK side).
* ``user.action``                   — high-level action signal
                                       (e.g. ``click``, ``submit``).

Unknown event types are recorded verbatim and ignored downstream
(forward compatibility — adding a new event type shouldn't break old
receivers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

RUM_SCHEMA_VERSION: Final[str] = "1"

RUM_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "run.start",
        "run.end",
        "page.view",
        "page.error",
        "network.request",
        "network.response",
        "network.failure",
        "console",
        "user.action",
    }
)


@dataclass(frozen=True, slots=True)
class RumEvent:
    """One parsed RUM event."""

    schema_version: str
    type: str
    seq: int
    ts: str  # ISO-8601 UTC, set by the SDK or the server.
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_known(self) -> bool:
        return self.type in RUM_EVENT_KINDS


def parse_event(raw: dict[str, Any]) -> RumEvent:
    """Parse a raw mapping into a :class:`RumEvent`.

    Tolerant: missing optional fields fall back to safe defaults so a
    sloppy SDK can't crash the receiver. The ``payload`` is the raw
    mapping minus the envelope keys, exactly like the synthetic event
    bridge does.
    """

    envelope_keys = {"schema_version", "type", "seq", "ts"}
    payload = {k: v for k, v in raw.items() if k not in envelope_keys}
    return RumEvent(
        schema_version=str(raw.get("schema_version", RUM_SCHEMA_VERSION)),
        type=str(raw.get("type", "unknown")),
        seq=int(raw.get("seq", 0)),
        ts=str(raw.get("ts", "")),
        payload=payload,
    )


__all__ = [
    "RUM_EVENT_KINDS",
    "RUM_SCHEMA_VERSION",
    "RumEvent",
    "parse_event",
]
