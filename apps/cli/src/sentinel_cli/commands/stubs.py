"""Stub command factory for unimplemented commands.

Stubs are reachable from `sentinel --help` (CLAUDE §13) but raise the
internal-error exit code (7) when invoked. The help text names the
phase where the real implementation lands so users can follow the plan.
"""

from __future__ import annotations

import typer
from engine.errors.base import InternalError


def register_stub(app: typer.Typer, *, name: str, phase: str, summary: str) -> None:
    """Attach a stub command to ``app``.

    The stub raises :class:`InternalError` (exit code 7) when invoked.
    This satisfies the spec in task 02.01: every PRD §13.1 command is
    registered, and the unimplemented ones surface a deterministic
    "not yet implemented" failure rather than silently doing nothing
    (CLAUDE §37: no fake completion).
    """

    help_text = f"{summary} (lands in Phase {phase})"

    @app.command(name=name, help=help_text)
    def _stub() -> None:
        # The CLI message points at the phase; the exception body carries
        # the structured detail the main() exception handler renders.
        raise InternalError(
            f"`sentinel {name}` is not yet implemented (lands in Phase {phase}).",
            technical_context={"command": name, "phase": phase},
            suggested_fix=(
                f"Track Phase {phase} in plans/STATUS.md. The command is "
                "registered here so help/--version behave correctly."
            ),
        )

    _stub.__name__ = f"_stub_{name.replace('-', '_')}"


__all__ = ["register_stub"]
