"""Safe chaos / adversarial testing module (, the documentation, ADR-0028).

Importing this package wires :class:`ChaosModule` into the default
orchestrator registry so ``sentinel chaos`` and ``sentinel audit``
(when ``modules.chaos = true``) both pick it up automatically.

Scenarios (the documentation):

- Network: slow_3g, offline, api_500, api_timeout.
- Session: expired token, missing permissions.
- UX: duplicate submit, double-click race, back/forward, refresh mid-flow.
- Data: empty dataset, large dataset, browser storage corruption.

Safety boundary:

- ``modules.chaos`` is OFF by default in :class:`ModulesConfig` — the
 scenarios above are surfaced only by explicit opt-in or via the CI
 ``nightly`` preset (the documentation).
- Session-claim manipulation runs Playwright-side only; the helpers
 never re-sign or forge production JWTs.
- No aggressive / evasion / detection-bypass knob exists on the CLI
 or in :class:`engine.config.schema.ChaosConfig`;
 ``tests/security/test_chaos_no_evasion_flags.py`` greps the package
 + CLI for compound forbidden literals and introspects the Typer
 parameters to keep that property.
"""

from __future__ import annotations

from modules.chaos.models import ChaosEvent, ChaosRunOutcome, ChaosScenarioResult
from modules.chaos.module import (
    ChaosModule,
    ChaosModuleOptions,
    register_with_default_registry,
)
from modules.chaos.scenarios import CATALOG, DEFAULT_CATEGORIES, ChaosScenario

register_with_default_registry()


__all__ = [
    "CATALOG",
    "DEFAULT_CATEGORIES",
    "ChaosEvent",
    "ChaosModule",
    "ChaosModuleOptions",
    "ChaosRunOutcome",
    "ChaosScenario",
    "ChaosScenarioResult",
    "register_with_default_registry",
]
