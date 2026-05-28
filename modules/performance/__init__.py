"""Performance audit module (Phase 12, PRD §10.5, CLAUDE.md §9, §27).

Importing this package wires :class:`PerformanceModule` into the default
orchestrator registry so ``sentinel perf`` and ``sentinel audit`` both
pick it up automatically.

The module exercises PRD §10.5 capabilities — LCP/CLS/INP page budgets,
API endpoint P95 budgets, JS bundle size, long-task (CPU blocking)
detection, and repeated-navigation stability — by invoking
``sentinel-ts audit-perf`` against each route in the discovery graph
(or the explicit ``--routes`` set).

Per CLAUDE §27, every finding description begins with "Synthetic
performance check" so consumers cannot mistake the lab measurement
for Real-User Monitoring. The forbidden-phrase guard in
``tests/security/test_synthetic_perf_labeling.py`` enforces this.
"""

from __future__ import annotations

from modules.performance.module import (
    PerformanceModule,
    PerformanceModuleOptions,
    register_with_default_registry,
)

register_with_default_registry()


__all__ = [
    "PerformanceModule",
    "PerformanceModuleOptions",
    "register_with_default_registry",
]
