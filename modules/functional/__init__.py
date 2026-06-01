"""Functional audit module (, the documentation, our engineering rules).

Importing this package wires :class:`FunctionalModule` into the default
orchestrator registry (``engine.orchestrator.registry.default_registry``)
so ``sentinel functional`` and ``sentinel audit`` both pick it up
automatically.

The functional module exercises the deterministic flows enumerated in
the documentation — login, signup, logout, password reset, CRUD, search /
filter / sort, role-based access, admin paths, file upload / download,
notification callbacks, and payment sandbox — by invoking the
Playwright runner against the specs the generator produced.

Failures translate into typed :class:`engine.domain.finding.Finding`
records with our product spec evidence; quarantined tests do not
block the quality gate.
"""

from __future__ import annotations

from modules.functional.module import (
    FunctionalModule,
    FunctionalModuleOptions,
    register_with_default_registry,
)

# Register on import. The default registry is process-wide, so doing this
# at import time means every CLI command that loads the orchestrator (e.g.
# `sentinel audit`, `sentinel functional`) picks up the module without
# extra wiring. The function is idempotent — re-importing is safe.
register_with_default_registry()


__all__ = [
    "FunctionalModule",
    "FunctionalModuleOptions",
    "register_with_default_registry",
]
