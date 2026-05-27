# Task 13.06 — Safe SQLi probe (sandbox/local only)

## Deliverables

- Disabled by default. Enabled only when `target.mode == "local"` OR `security.mode == "authorized_destructive"` with proof.
- Probe technique:
  - Sends boolean-based and time-based payloads with hard timeouts (no resource exhaustion).
  - Uses a curated, minimal set.
  - Compares responses for behavioral differences (status, body length, response time).
- Severity critical when confirmed.
- Audit-logged per request.

## Acceptance criteria

- Fixture with sandbox SQLi endpoint triggers finding only when allowed by mode.
- Public-target attempt without proof refused.

## Tests required

- `tests/integration/modules/security/test_sqli_local.py`.
- `tests/integration/modules/security/test_sqli_refusal_public.py`.

## PRD / CLAUDE.md references

- PRD §10.7, §2.
- CLAUDE.md §6, §26.

## Definition of Done

- [ ] Probe + gates + audit log.
- [ ] `STATUS.md` updated.
