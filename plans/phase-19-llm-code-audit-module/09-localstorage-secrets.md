# Task 19.09 — Tokens in localStorage / sessionStorage

## Deliverables

- After authenticated flows, dump `localStorage` + `sessionStorage` keys/values; run them through the redaction-rule detector (Phase 01) in **detection** mode.
- If any value matches `jwt`, `bearer_token`, generic high-entropy → finding `LLM-CLIENT-SECRET-STORAGE`, severity medium-high.
- Cross-references Phase 13.08 (frontend secrets).

## Acceptance criteria

- Fixture storing JWT in localStorage → finding.

## Tests required

- `tests/integration/modules/llm_audit/test_localstorage_secrets.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31, §33.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
