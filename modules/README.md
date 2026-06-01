# modules/

Pluggable audit modules. our product spec, §10, §22.

Each module follows the contract in our engineering rules: `validate prerequisites → plan checks → execute checks → collect evidence → emit findings → emit metrics → summarize result`.

- `functional/` — login/signup/CRUD/role/admin (the documentation; Phase 10).
- `api/` — OpenAPI/GraphQL contract + negative cases (the documentation; Phase 22).
- `accessibility/` — axe-core, keyboard, landmarks (the documentation; Phase 11).
- `performance/` — LCP/CLS/INP, bundle/API budgets (the documentation; Phase 12).
- `visual/` — baseline diffs (the documentation; Phase 21).
- `security/` — safe-by-default OWASP checks; allowlist enforced (the documentation; Phase 13).
- `chaos/` — slow network, offline, timeouts, session edges (the documentation; Phase 23).
- `llm_audit/` — dead buttons, fake routes, mock-data shipped, frontend-only auth (the documentation, §31; Phase 19).

Modules MUST NOT control global run lifecycle. A module failure produces a typed partial result unless it invalidates the whole run.
