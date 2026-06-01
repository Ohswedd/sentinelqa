"""Pretty-printers for SentinelQA errors at the CLI boundary.

Two output modes:

- ``human``: indented, optional ANSI color, includes the suggested fix on
  its own line. Used by interactive ``sentinel`` invocations.
- ``json``: single-line JSON dict matching ``to_agent_message()``. Used by
  ``--json`` / ``--ci`` modes; never emits ANSI.

our engineering guidelines forbids verbose stack traces by default — they are gated
behind the ``verbose`` flag.
"""

from __future__ import annotations

import json
import traceback
from typing import Literal

from engine.errors.base import SentinelError

RenderMode = Literal["human", "json"]


def render_error(
    error: SentinelError,
    *,
    mode: RenderMode = "human",
    verbose: bool = False,
    color: bool = False,
) -> str:
    """Render ``error`` for terminal output.

    Returns the rendered string; the caller is responsible for choosing
    stdout vs stderr (the CLI shell writes errors to stderr unless the
    caller is in ``--json`` mode, in which case the error rides stdout as
    the only line of output).
    """

    if mode == "json":
        payload = error.to_agent_message()
        if verbose:
            # Only attach a redacted stack when explicitly requested; even
            # then the trace is best-effort because `error` may have been
            # constructed without a __traceback__.
            tb = error.__traceback__
            if tb is not None:
                payload["traceback"] = "".join(traceback.format_exception(type(error), error, tb))
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    # human mode
    title = f"{error.code}: {error.message}"
    fix = f"  Suggested fix: {error.suggested_fix}" if error.suggested_fix else ""
    parts = [title]
    if fix:
        parts.append(fix)
    if error.technical_context:
        # Keep the context output stable across runs to help diffing.
        ctx_lines = [f"    {k} = {v!r}" for k, v in sorted(error.technical_context.items())]
        parts.append("  Context:")
        parts.extend(ctx_lines)
    if verbose and error.__traceback__ is not None:
        parts.append("  Traceback:")
        for line in traceback.format_exception(type(error), error, error.__traceback__):
            parts.append("    " + line.rstrip("\n"))

    rendered = "\n".join(parts)
    if color:
        # Bold red for the title only; we deliberately do not depend on a
        # color library — ANSI codes are cheap and avoid runtime deps.
        rendered = rendered.replace(title, f"\033[1;31m{title}\033[0m", 1)
    return rendered


__all__ = ["render_error", "RenderMode"]
