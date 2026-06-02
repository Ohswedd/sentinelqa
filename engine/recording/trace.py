# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Recording trace parser.

Input shape (compatible with a saved ``playwright codegen`` action log
or hand-authored equivalents):

.. code-block:: json

    {
      "schema_version": "1",
      "name": "checkout-happy-path",
      "base_url": "https://shop.example.com",
      "priority": "p0",
      "steps": [
        {"action": "navigate", "url": "https://shop.example.com/"},
        {"action": "click",    "selector": "#add-to-cart"},
        {"action": "fill",     "selector": "#email", "value": "user@example.com"},
        {"action": "press",    "selector": "#email", "key": "Enter"},
        {"action": "expect",   "selector": "#thank-you", "assertion": "visible"}
      ]
    }

Supported actions for the MVP: ``navigate``, ``click``, ``dblclick``,
``fill``, ``press``, ``select``, ``check``, ``uncheck``, ``hover``,
``wait_for``, ``expect``. Unknown actions raise — we'd rather fail
loud than silently drop steps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

RECORDING_SCHEMA_VERSION: Final[str] = "1"

RecordedAction = Literal[
    "navigate",
    "click",
    "dblclick",
    "fill",
    "press",
    "select",
    "check",
    "uncheck",
    "hover",
    "wait_for",
    "expect",
]

_SUPPORTED_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "navigate",
        "click",
        "dblclick",
        "fill",
        "press",
        "select",
        "check",
        "uncheck",
        "hover",
        "wait_for",
        "expect",
    }
)


@dataclass(frozen=True, slots=True)
class RecordingStep:
    """One action recorded by the operator."""

    action: RecordedAction
    selector: str | None = None
    url: str | None = None
    value: str | None = None
    key: str | None = None
    assertion: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RecordingTrace:
    """A parsed recording: ordered steps + metadata."""

    schema_version: str
    name: str
    base_url: str
    priority: str
    steps: tuple[RecordingStep, ...]


def parse_trace(payload: dict[str, Any] | Path) -> RecordingTrace:
    """Parse a trace mapping or a path pointing at a JSON file."""

    data = json.loads(payload.read_text(encoding="utf-8")) if isinstance(payload, Path) else payload

    if not isinstance(data, dict):
        raise ValueError("recording trace must be a mapping at the top level")

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("recording trace missing required 'name' field")
    base_url = str(data.get("base_url", "")).strip()
    if not base_url:
        raise ValueError("recording trace missing required 'base_url' field")

    priority = str(data.get("priority", "p3")).strip().lower()
    if priority not in {"p0", "p1", "p2", "p3"}:
        raise ValueError(f"priority must be p0..p3; got {priority!r}")

    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("recording trace must carry at least one step")

    steps = tuple(_parse_step(idx, entry) for idx, entry in enumerate(raw_steps))
    return RecordingTrace(
        schema_version=str(data.get("schema_version", RECORDING_SCHEMA_VERSION)),
        name=name,
        base_url=base_url,
        priority=priority,
        steps=steps,
    )


def _parse_step(idx: int, entry: object) -> RecordingStep:
    if not isinstance(entry, dict):
        raise ValueError(f"step {idx}: must be a mapping")
    action_raw = entry.get("action")
    if action_raw not in _SUPPORTED_ACTIONS:
        raise ValueError(
            f"step {idx}: unsupported action {action_raw!r}; "
            f"supported: {sorted(_SUPPORTED_ACTIONS)}"
        )
    return RecordingStep(
        action=action_raw,
        selector=_str_or_none(entry.get("selector")),
        url=_str_or_none(entry.get("url")),
        value=_str_or_none(entry.get("value")),
        key=_str_or_none(entry.get("key")),
        assertion=_str_or_none(entry.get("assertion")),
        payload={
            k: v
            for k, v in entry.items()
            if k not in {"action", "selector", "url", "value", "key", "assertion"}
        },
    )


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


__all__ = [
    "RECORDING_SCHEMA_VERSION",
    "RecordedAction",
    "RecordingStep",
    "RecordingTrace",
    "parse_trace",
]
