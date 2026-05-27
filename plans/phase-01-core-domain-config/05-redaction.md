# Task 01.05 — Redaction utilities

## Objective

Replace the Phase 00 stub of `engine/policy/redaction.py` with a real implementation that scrubs every sensitive category from CLAUDE §33 before logs, reports, agent messages, or audit entries leave the process.

## Prerequisites

- Tasks 01.01 and 01.04 complete.

## Deliverables

- `engine/policy/redaction.py` exposing:
  - `redact(value: Any, *, depth: int = 6) -> Any` — recursively scrubs strings, dicts, lists, and tuples. Replaces detected secrets with `"[REDACTED:<category>]"`.
  - `redact_headers(headers: Mapping[str, str]) -> dict[str, str]` — case-insensitive scrubber for HTTP headers; always redacts `authorization`, `cookie`, `set-cookie`, `proxy-authorization`, `x-api-key`, `x-auth-token`, `api-key`.
  - `redact_url(url: str) -> str` — strips userinfo and query secrets (`token`, `access_token`, `apikey`, `signature`, `sig`).
  - `RedactionRule` dataclass with `category: str`, `pattern: re.Pattern`, `description: str`.
- A built-in rule set covering: passwords, bearer tokens, OAuth tokens, JWTs, AWS keys (AKIA…, ASIA…), GCP service-account JSON, Anthropic/OpenAI/Stripe keys (`sk-`/`pk-`), private keys (PEM blocks), session IDs, CSRF tokens, generic high-entropy tokens (entropy threshold + length).
- Allowlist mechanism: configurable per-run "do-not-redact" tokens for false-positive control (used only when the user explicitly opts in via config; never enabled in CI by default).
- Performance: redact a 5 MB JSON document in under 1 second on a developer laptop.

## Steps

1. Implement the rule registry; load built-in rules at import time.
2. Implement `redact()` with depth-limited recursion (default 6) to avoid pathological inputs.
3. Implement `redact_headers()` and `redact_url()`.
4. Add a Shannon-entropy helper for generic-token detection; tune threshold against fixtures of real-looking-but-fake tokens.
5. Add property-based tests (hypothesis) generating random JSON structures and asserting:
   - Output is JSON-serializable.
   - No string matching the rule patterns survives.
   - Non-secret strings are unchanged.
6. Hook redaction into the logger from task 01.06 and the audit log from task 01.03.

## Acceptance criteria

- A payload containing `{"password": "hunter2", "ok": "yes"}` becomes `{"password": "[REDACTED:password]", "ok": "yes"}`.
- A header dict with `Authorization: Bearer abc.def.ghi` becomes `Authorization: [REDACTED:bearer_token]`.
- A URL `https://api.example.com/x?token=secret` becomes `https://api.example.com/x?token=[REDACTED:url_token]`.
- Hypothesis property tests pass for 10 000 examples.
- Benchmark `pytest -m bench tests/unit/policy/test_redaction_perf.py` passes within budget.

## Tests required

- `tests/unit/policy/test_redaction.py` — every CLAUDE §33 category has at least two positive and two negative cases.
- `tests/unit/policy/test_redaction_perf.py` — benchmark.
- Hypothesis property tests.

## PRD / CLAUDE.md references

- PRD §20 Evidence and Reporting.
- CLAUDE.md §33 Logging & secrets.

## Definition of Done

- [ ] All categories from CLAUDE §33 covered.
- [ ] Hypothesis suite green.
- [ ] Performance within budget.
- [ ] Logger and audit-log paths use redaction.
- [ ] `STATUS.md` updated.
