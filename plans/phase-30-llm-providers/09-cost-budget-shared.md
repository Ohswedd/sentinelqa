# Task 30.09 — Shared cost / budget / rate-limit plumbing

## Deliverables

- `engine/llm/budget.py` exposes a single per-run `LlmBudget` instance
  attached to `LifecycleContext` at run-init time. Every adapter that
  posts to a remote endpoint must consult the budget *before* sending
  and *after* receiving (final cost may exceed estimate).
- `engine/llm/rate_limit.py` — token-bucket per provider, default
  `60 req/min`, overridable via config.
- Config additions:
  - `llm.budget.max_usd_per_run` (default `0.50`).
  - `llm.budget.max_usd_per_phase` (planner / analyzer / healer each
    have their own override; default inherits from `max_usd_per_run`).
  - `llm.rate_limit.requests_per_minute` (default `60`).
- `BudgetExceededError` extends `SentinelError`, exits `E-LLM-003`, and
  the lifecycle catches it gracefully: the caller falls back to the
  deterministic path and the run records the partial LLM contribution.
- Audit log entries `llm.request` / `llm.response` carry: `provider`,
  `model`, `caller`, `tokens_in`, `tokens_out`, `cost_usd`,
  `cumulative_usd`, `latency_ms` — redacted (no prompts in the log).

## Tests required

- `tests/unit/llm/test_budget_shared.py` — pre-check, post-check,
  overrun raises, partial accounting.
- `tests/unit/llm/test_rate_limit.py` — bucket fills, denies, refills.
- `tests/integration/llm/test_audit_log_entries.py` — every call writes
  exactly one paired request/response entry to `audit.log`, no prompt
  text, no key, no full URL.

## Definition of Done

- [ ] Single budget enforcement point; planner/analyzer/healer all go
      through it.
- [ ] Audit log includes provider + cost on every call.
- [ ] `STATUS.md` updated.
