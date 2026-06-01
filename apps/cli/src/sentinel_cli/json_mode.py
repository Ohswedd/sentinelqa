"""Strict JSON-mode helpers.

``json_stdout()`` is the only sanctioned way to emit machine-readable
output. While the context is active:

- stdout receives only the JSON objects passed to :func:`emit`.
- ANSI escapes are suppressed.
- A test-only env-var guard (``SENTINELQA_ASSERT_JSON_STDOUT=1``)
 installs a write hook that fails the process if any non-JSON byte
 reaches stdout — used in CLI tests to prove invariants without
 cluttering production with assertions.

Logging configuration (engine.log.configure_logging) is the gatekeeper
for log streams; this module assumes the caller already chose ``json``
or ``quiet`` mode there.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, TextIO, cast

_ENV_ASSERT = "SENTINELQA_ASSERT_JSON_STDOUT"


class _StrictJsonStream:
    """Wraps a TextIO so only `emit()` may write, and only JSON lines."""

    def __init__(self, target: TextIO) -> None:
        self._target = target

    def emit(self, obj: object) -> None:
        line = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str)
        self._target.write(line + "\n")
        self._target.flush()


@contextmanager
def json_stdout() -> Generator[_StrictJsonStream, None, None]:
    """Yield a JSON-only emitter for stdout.

    The original stdout is preserved; nothing is monkey-patched on
    success. When ``SENTINELQA_ASSERT_JSON_STDOUT=1`` we install a write
    hook that aborts the process if anything other than a JSON line is
    written to stdout via direct ``print``/``sys.stdout.write`` — this
    is a test-time invariant check (CLAUDE §13: JSON mode must output
    only machine-readable JSON).
    """

    target: TextIO = sys.stdout
    if os.environ.get(_ENV_ASSERT, "").lower() in {"1", "true", "yes"}:
        guarded = _GuardedTextIO(sys.stdout)
        target = cast(TextIO, guarded)
        sys.stdout = target
    try:
        yield _StrictJsonStream(target)
    finally:
        if isinstance(target, _GuardedTextIO):
            sys.stdout = target.unwrap()


class _GuardedTextIO:
    """Test-only wrapper that fails fast on non-JSON stdout writes."""

    def __init__(self, target: TextIO) -> None:
        self._target = target
        self._buffer = ""

    def write(self, data: str) -> int:
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line == "":
                continue
            try:
                json.loads(line)
            except ValueError as exc:
                raise AssertionError(
                    f"JSON-mode purity violated: non-JSON line on stdout: {line!r}"
                ) from exc
        return self._target.write(data)

    def flush(self) -> None:
        self._target.flush()

    def isatty(self) -> bool:
        return False

    def unwrap(self) -> TextIO:
        if self._buffer.strip():
            try:
                json.loads(self._buffer)
            except ValueError as exc:
                raise AssertionError(
                    f"JSON-mode purity violated: trailing non-JSON on stdout: {self._buffer!r}"
                ) from exc
        return self._target

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


def emit(stream: _StrictJsonStream, obj: object) -> None:
    """Sugar for tests; identical to ``stream.emit(obj)``."""

    stream.emit(obj)


__all__ = ["json_stdout", "emit"]
