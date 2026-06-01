# engine/

The SentinelQA orchestration core. our product spec, §11.2.

- `orchestrator/` — run lifecycle (our product spec, CLAUDE §10;).
- `discovery/` — DOM/route/API discovery (the documentation;).
- `planner/` — test plan generation (the documentation;).
- `generator/` — Playwright spec generation (the documentation;).
- `runner/` — local + Docker runner (the documentation;).
- `analyzer/` — failure categorization (the documentation;).
- `healer/` — self-repair proposals (the documentation;).
- `reporter/` — finding aggregation, JSON/HTML/JUnit/SARIF (the documentation, §20; and 15).
- `policy/` — safety policy, target allowlist, redaction (our product spec, §23;).

Core domain code in this folder MUST NOT depend on Typer, Click, FastAPI, Playwright, GitHub Actions, BrowserStack, or LLM SDKs. External tools live behind adapters under `packages/` or `integrations/`.
