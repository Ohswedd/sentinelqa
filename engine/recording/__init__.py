# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Recording-driven test generation (v1.9.0, phase 39).

Take a structured browser recording — for now, the JSON produced by
``playwright codegen`` saved with ``--output trace.json`` or a
hand-authored trace following the same schema — and emit a
SentinelQA-tagged Playwright spec.

Why we don't ship a bundled recorder UI yet
-------------------------------------------

Playwright already ships a high-quality codegen recorder
(``playwright codegen``). Re-implementing the recorder UI is a
multi-quarter project that doesn't unlock new value. What's new in
SentinelQA is the *spec generator* — translating a recording into a
spec that fits the same flow-id / priority / page-object layout the
audit module generates, so the recorded test runs alongside generated
ones with identical reporter / scoring behaviour.

The post-condition stub is a seam: when the LLM module is configured,
``suggest_postconditions`` calls it for each recorded step and adds
the suggested assertions. With no LLM, we add a sensible default
(presence-of-result page checks).
"""

from __future__ import annotations

from engine.recording.postconditions import (
    PostconditionSuggester,
    default_postconditions,
)
from engine.recording.spec_emitter import emit_spec
from engine.recording.trace import (
    RECORDING_SCHEMA_VERSION,
    RecordingStep,
    RecordingTrace,
    parse_trace,
)

__all__ = [
    "RECORDING_SCHEMA_VERSION",
    "PostconditionSuggester",
    "RecordingStep",
    "RecordingTrace",
    "default_postconditions",
    "emit_spec",
    "parse_trace",
]
