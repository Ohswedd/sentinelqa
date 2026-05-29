"""Visual-regression audit module (Phase 21, PRD §10.6, CLAUDE.md §29).

Importing this package wires :class:`VisualModule` into the default
orchestrator registry so ``sentinel visual`` and ``sentinel audit``
both pick it up automatically.

The module consumes PNGs already captured into the run's
``visual/current/<viewport>/<route-slug>.png`` tree, diffs them against
the baselines under ``visual.baselines_dir``, and emits one
:class:`Finding` per route+viewport whose pixel-diff fraction exceeds
``visual.threshold`` (and, when ``visual.perceptual.enabled``, also
falls below ``visual.perceptual.min_similarity``).

Baselines never auto-accept in CI: the :func:`apps/cli sentinel visual`
``accept`` subcommand refuses to promote ``current`` PNGs when the
``--ci`` flag is set or ``CI`` / ``SENTINEL_CI`` is truthy in the
environment (PRD §10.6, CLAUDE §29, §39).

ADR-0026 documents the storage layout, the diff algorithm, the masking
contract, and the CI-acceptance guard.
"""

from __future__ import annotations

from modules.visual.module import (
    VisualModule,
    VisualModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "VisualModule",
    "VisualModuleOptions",
    "register_with_default_registry",
]
