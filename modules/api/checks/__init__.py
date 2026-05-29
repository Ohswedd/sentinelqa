"""Per-check runners for the API module (Phase 22).

Each module in this package exposes ``run_<check>_check(...)`` returning
:class:`modules.api.models.ApiCheckResult`. Checks are pure functions
of ``(client, doc/schema, config)`` so they're trivially unit-testable
without spinning up the orchestrator.
"""
