"""SentinelQA audit modules (our product spec, §10, our engineering rules).

Each subpackage implements one capability module (onward).
Importing this package exposes the modules namespace so the orchestrator
can `import modules.functional` (etc.) to trigger the per-module
``register_module`` side effect.

will introduce entry-point discovery; until then, registration
happens on import.
"""
