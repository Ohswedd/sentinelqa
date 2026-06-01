# modules/

Pluggable audit modules. our product spec, §10, §22.

Each module follows the contract in our engineering rules: `validate prerequisites → plan checks → execute checks → collect evidence → emit findings → emit metrics → summarize result`.

- `functional/` — login/signup/CRUD/role/admin (the documentation;).
- `api/` — OpenAPI/GraphQL contract + negative cases (the documentation;).
- `accessibility/` — axe-core, keyboard, landmarks (the documentation;).
- `performance/` — LCP/CLS/INP, bundle/API budgets (the documentation;).
- `visual/` — baseline diffs (the documentation;).
- `security/` — safe-by-default OWASP checks; allowlist enforced (the documentation;).
- `chaos/` — slow network, offline, timeouts, session edges (the documentation;).
- `llm_audit/` — dead buttons, fake routes, mock-data shipped, frontend-only auth (the documentation, §31;).

Modules MUST NOT control global run lifecycle. A module failure produces a typed partial result unless it invalidates the whole run.
