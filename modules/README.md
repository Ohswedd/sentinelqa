# modules/

Pluggable audit modules. PRD §9, §10, §22.

Each module follows the contract in `CLAUDE.md` §9: `validate prerequisites → plan checks → execute checks → collect evidence → emit findings → emit metrics → summarize result`.

- `functional/` — login/signup/CRUD/role/admin (PRD §10.1; Phase 10).
- `api/` — OpenAPI/GraphQL contract + negative cases (PRD §10.3; Phase 22).
- `accessibility/` — axe-core, keyboard, landmarks (PRD §10.4; Phase 11).
- `performance/` — LCP/CLS/INP, bundle/API budgets (PRD §10.5; Phase 12).
- `visual/` — baseline diffs (PRD §10.6; Phase 21).
- `security/` — safe-by-default OWASP checks; allowlist enforced (PRD §10.7; Phase 13).
- `chaos/` — slow network, offline, timeouts, session edges (PRD §10.8; Phase 23).
- `llm_audit/` — dead buttons, fake routes, mock-data shipped, frontend-only auth (PRD §10.9, §31; Phase 19).

Modules MUST NOT control global run lifecycle. A module failure produces a typed partial result unless it invalidates the whole run.
