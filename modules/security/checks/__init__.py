"""Individual security checks.

Every check is implemented as a small function that takes a
:class:`CheckContext` and returns a :class:`SecurityCheckResult`. The
module orchestrator picks the set of enabled checks (per config +
options + safety policy), runs each through
:func:`SafetyPolicy.enforce` first, and aggregates the results.

Checks never depend on each other; they share only the
:class:`CheckContext` and the shared HTTP client.
"""

from __future__ import annotations

from modules.security.checks.context import CheckContext

__all__ = ["CheckContext"]
