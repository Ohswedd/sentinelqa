# Task 19.07 — UI-only auth / role gates

## Deliverables

- Use Phase 05 auth boundary detection. For every route the UI hides from a low-priv user, send an authenticated request as that user to the **backend** for that route AND for any APIs the UI used on the admin page. If the backend serves them (200) → finding `LLM-UI-ONLY-AUTH`, severity critical.
- Same applies to role-based actions: low-priv user can call admin-only API → critical IDOR-style finding (cross-references Phase 13.07).

## Acceptance criteria

- Fixture where `/admin` is hidden in UI but reachable by API for a regular user → critical finding.

## Tests required

- `tests/integration/modules/llm_audit/test_ui_only_auth.py`.

## PRD / CLAUDE.md references

- PRD §10.9.
- CLAUDE.md §31.

## Definition of Done

- [ ] Check implemented + tested.
- [ ] `STATUS.md` updated.
