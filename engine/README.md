# engine/

The SentinelQA orchestration core. our product spec, §11.2.

- `orchestrator/` — run lifecycle (our product spec, CLAUDE §10; Phase 02).
- `discovery/` — DOM/route/API discovery (the documentation; Phase 05).
- `planner/` — test plan generation (the documentation; Phase 06).
- `generator/` — Playwright spec generation (the documentation; Phase 07).
- `runner/` — local + Docker runner (the documentation; Phase 08).
- `analyzer/` — failure categorization (the documentation; Phase 09).
- `healer/` — self-repair proposals (the documentation; Phase 20).
- `reporter/` — finding aggregation, JSON/HTML/JUnit/SARIF (the documentation, §20; Phases 03 and 15).
- `policy/` — safety policy, target allowlist, redaction (our product spec, §23; Phase 01).

Core domain code in this folder MUST NOT depend on Typer, Click, FastAPI, Playwright, GitHub Actions, BrowserStack, or LLM SDKs . External tools live behind adapters under `packages/` or `integrations/`.
