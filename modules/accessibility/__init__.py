"""Accessibility audit module (Phase 11, PRD §10.4, CLAUDE.md §9, §28).

Importing this package wires :class:`AccessibilityModule` into the
default orchestrator registry so ``sentinel a11y`` and ``sentinel audit``
both pick it up automatically.

The module exercises PRD §10.4 capabilities — axe-core integration,
keyboard navigation, focus order, missing labels, ARIA misuse, contrast
checks, modal traps, form errors, landmark structure, and screen-reader
name detection — by invoking ``sentinel-ts audit-a11y`` against each
route in the discovery graph (or the explicit ``--routes`` set).

Per CLAUDE §28, descriptions always begin with "Automated accessibility
check found" and full-compliance phrasing is forbidden. The guard test
in ``tests/security/test_no_wcag_compliance_claims.py`` enforces this.
"""

from __future__ import annotations

from modules.accessibility.module import (
    AccessibilityModule,
    AccessibilityModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "AccessibilityModule",
    "AccessibilityModuleOptions",
    "register_with_default_registry",
]
