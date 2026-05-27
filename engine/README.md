# engine/

The SentinelQA orchestration core. PRD §9, §11.2.

- `orchestrator/` — run lifecycle (PRD §10, CLAUDE §10; Phase 02).
- `discovery/` — DOM/route/API discovery (PRD §9.1; Phase 05).
- `planner/` — test plan generation (PRD §9.2; Phase 06).
- `generator/` — Playwright spec generation (PRD §9.3; Phase 07).
- `runner/` — local + Docker runner (PRD §9.4; Phase 08).
- `analyzer/` — failure categorization (PRD §9.5; Phase 09).
- `healer/` — self-repair proposals (PRD §9.6; Phase 20).
- `reporter/` — finding aggregation, JSON/HTML/JUnit/SARIF (PRD §9.7, §20; Phases 03 and 15).
- `policy/` — safety policy, target allowlist, redaction (PRD §2, §23; Phase 01).

Core domain code in this folder MUST NOT depend on Typer, Click, FastAPI, Playwright, GitHub Actions, BrowserStack, or LLM SDKs (`CLAUDE.md` §7). External tools live behind adapters under `packages/` or `integrations/`.
