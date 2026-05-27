# Phase 29 — Final Hardening & PRD Reconciliation

## Objective

A whole-project audit before declaring SentinelQA done: safety boundary, secret-leak, determinism, performance, accessibility of our own outputs, every PRD section accounted for, every CLAUDE.md rule honored, every gate row in `STATUS.md` filled.

## PRD / CLAUDE.md references

- All of PRD.
- All of CLAUDE.md.

## Sub-phases & tasks

1. `01-safety-audit.md` — Re-audit PRD §2 / CLAUDE §6 across all modules.
2. `02-secret-leak-audit.md` — Sweep artifacts, logs, reports for unredacted secrets.
3. `03-determinism-audit.md` — Re-run scoring + reports N times; confirm byte-equal.
4. `04-performance-audit.md` — Self-audit the tool: import time, full-audit time on Next.js example.
5. `05-accessibility-of-outputs.md` — Self-axe on our HTML report; PR comment Markdown renders cleanly.
6. `06-prd-coverage.md` — Walk every PRD section; mark "implemented in Phase X" or "ADR explains why deferred".
7. `07-claude-md-coverage.md` — Walk every CLAUDE.md rule; confirm enforcement.
8. `08-definition-of-done-sweep.md` — Tests, lint, type, docs, schemas, audit log, no secrets.
9. `09-status-md-final.md` — Every phase gate signed; deferred-scope register empty.

## Definition of Done

- All checks pass.
- `STATUS.md` shows 30/30 phases complete with signed gate rows.
- PRD + CLAUDE.md reflect reality.

## Phase Gate Review

- [ ] Safety audit clean.
- [ ] Secret-leak audit clean.
- [ ] Determinism audit clean.
- [ ] Performance and self-a11y meet targets.
- [ ] PRD + CLAUDE.md fully reconciled.
- [ ] `STATUS.md` updated; Phase 29 is the last gate.
