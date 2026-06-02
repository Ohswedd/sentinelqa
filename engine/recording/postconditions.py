# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""LLM-suggested post-conditions (v1.9.0 stub).

The MVP ships:

* a callable Protocol (:class:`PostconditionSuggester`) the recording
  pipeline calls per-step / per-trace;
* a deterministic default (:func:`default_postconditions`) that
  inspects the last few recorded steps and proposes presence checks
  for any selector that was filled / clicked at the end of the flow.

A real LLM implementation lives in `engine.llm.*`; wiring it here is a
follow-up. The seam is in place so a custom suggester drops in via:

    spec_path = emit_spec(
        trace,
        output_dir=...,
        postconditions=my_llm_suggester(trace),
    )
"""

from __future__ import annotations

from typing import Protocol

from engine.recording.trace import RecordingTrace


class PostconditionSuggester(Protocol):
    """Callable that turns a recording into Playwright expect expressions."""

    def __call__(self, trace: RecordingTrace) -> tuple[str, ...]: ...


def default_postconditions(trace: RecordingTrace) -> tuple[str, ...]:
    """Deterministic post-condition stub.

    Returns up to two ``page.locator(...)`` expressions naming the
    selectors involved in the last interactive step (click / fill /
    press). The spec emitter wraps each with ``await expect(...).toBeVisible()``.
    """

    selectors: list[str] = []
    for step in reversed(trace.steps):
        if step.selector is None:
            continue
        if step.action in {"click", "fill", "press", "select"} and step.selector not in selectors:
            selectors.append(step.selector)
        if len(selectors) >= 2:
            break

    return tuple(f"page.locator('{sel}')" for sel in selectors)


__all__ = ["PostconditionSuggester", "default_postconditions"]
