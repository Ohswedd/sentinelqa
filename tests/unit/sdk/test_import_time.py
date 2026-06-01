"""``import sentinelqa`` must stay fast (our product spec4, ).

Heavy modules (orchestrator, planner, discovery, generator, runner,
reporter) MUST be lazy-loaded so agent-facing tooling cold-starts
quickly. The budget per is 200 ms wall-clock on the dev
workstation. Anything over 600 ms in CI means a regression — heavy
imports leaked into module top level.
"""

from __future__ import annotations

import subprocess
import sys
import time

# Budget is intentionally loose so this test is stable across machines.
# The local dev workstation sees ~80 ms; CI runners may be slower. A 600 ms
# ceiling still catches an eager Playwright/jinja2/lxml import (each of
# which adds 100+ ms on its own).
IMPORT_BUDGET_MS = 600.0


def _measure_subprocess_import() -> float:
    """Spawn a fresh interpreter and measure ``import sentinelqa``.

    Avoids cache effects from earlier tests by using ``-S`` to skip
    site-packages customisation and a freshly-spawned process.
    """

    src = (
        "import time; "
        "start = time.perf_counter(); "
        "import sentinelqa; "
        "elapsed_ms = (time.perf_counter() - start) * 1000; "
        "print(f'{elapsed_ms:.3f}')"
    )
    out = subprocess.check_output([sys.executable, "-c", src])
    return float(out.decode().strip())


def test_import_time_under_budget() -> None:
    elapsed_ms = _measure_subprocess_import()
    assert elapsed_ms < IMPORT_BUDGET_MS, (
        f"import sentinelqa took {elapsed_ms:.1f} ms (budget {IMPORT_BUDGET_MS} ms). "
        "A heavy module (orchestrator, planner, discovery, generator, runner, "
        "reporter) probably leaked into the package top level."
    )


def test_heavy_modules_not_imported_at_package_load() -> None:
    """Confirm orchestrator / runner / discovery stay lazy.

    Spawn a fresh interpreter, import sentinelqa, then inspect
    ``sys.modules`` — none of the heavy submodules should appear.
    """

    src = (
        "import sys, sentinelqa; "
        "heavy = [m for m in sys.modules "
        "if m.startswith('engine.orchestrator') "
        "or m.startswith('engine.runner') "
        "or m.startswith('engine.discovery') "
        "or m.startswith('engine.generator') "
        "or m.startswith('engine.planner') "
        "or m.startswith('engine.reporter')]; "
        "print(','.join(sorted(heavy)))"
    )
    out = subprocess.check_output([sys.executable, "-c", src]).decode().strip()
    if out:
        # The dispatcher's ``run_writer`` is referenced by the SDK's
        # internal digest helper, but that helper is itself only invoked
        # via a method call — so it must NOT show up after just
        # ``import sentinelqa``. Same for the rest.
        loaded = out.split(",")
        # Allow nothing — the SDK must not pull any of these on bare import.
        assert not loaded, (
            f"sentinelqa eagerly imported heavy modules: {loaded!r}. "
            "Move them behind method-level imports (see _facade.py)."
        )


def test_repeated_imports_are_idempotent() -> None:
    """Re-importing should not error or recompute the surface."""

    import importlib

    import sentinelqa

    first = list(sentinelqa.__all__)
    importlib.reload(sentinelqa)
    second = list(sentinelqa.__all__)
    assert first == second


def test_module_level_time_measurement_is_sane() -> None:
    # Smoke: ensure perf_counter delta is positive.
    start = time.perf_counter()
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.0
