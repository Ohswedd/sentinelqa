# Phase 20 — Healer / Self-Repair Module

## Objective

Implement conservative test self-repair (PRD §9.6, §23 self-healing rules / CLAUDE §23): propose locator updates, wait condition improvements, fixture refreshes, and assertion stabilizations. **Never** weaken assertions silently or remove tests. Every proposal carries confidence and a `requires_human_review` flag.

## PRD / CLAUDE.md references

- PRD §9.6 Healer.
- CLAUDE.md §23 Self-healing rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `HealerModule`.
2. `02-locator-repair.md` — Replace failed semantic locator with the next best candidate using descriptors.
3. `03-wait-condition-improvement.md` — Replace timeouts with explicit waits.
4. `04-fixture-refresh.md` — Repair stale fixture data.
5. `05-repair-proposal-schema.md` — Schema for proposals.
6. `06-human-review-gating.md` — Categorize auto-apply vs review-required.
7. `07-fix-cli.md` — `sentinel fix` command.
8. `08-verify-fix-integration.md` — Wire to MCP verify_fix (Phase 18).
9. `09-tests.md` — sweep.

## Definition of Done

- Repairs categorized by confidence; only `confidence ≥ threshold` auto-applies (configurable).
- No test removed by the healer.
- No assertion weakened without explicit `--allow-weaken` flag + audit log entry.

## Phase Gate Review

- [ ] Repair proposals schema-validated.
- [ ] Auto-apply gate works.
- [ ] Hand-edited tests are never overwritten by the healer.
- [ ] ADR-0019 (Self-healing policy) committed.
- [ ] `STATUS.md` updated.
