"""SentinelQA audit modules (PRD §9, §10, CLAUDE.md §9).

Each subpackage implements one capability module (Phase 10 onward).
Importing this package exposes the modules namespace so the orchestrator
can `import modules.functional` (etc.) to trigger the per-module
``register_module`` side effect.

Phase 24 will introduce entry-point discovery; until then, registration
happens on import.
"""
