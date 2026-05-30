# Task 34.04 — SOC 2 audit-trail quality gate

## Deliverables

- `modules/compliance/soc2_trail.py`:
  - At end-of-run, audit the run's own `audit.log`. Assert:
    1. Every safety-policy decision is recorded.
    2. Every module start / end is recorded.
    3. Every artifact emission is recorded.
    4. Every LLM call (Phase 30.09) is recorded with provider + cost.
    5. Every vault access (Phase 31.07) is recorded.
    6. The file is JSONL, parseable, append-only (no edits to prior
       lines).
    7. No cookie / secret / Authorization-header value is present
       (re-uses Phase 29.02 secret-leak rules).
  - Emit a `<run_dir>/compliance/soc2_trail.json` summary with the
    seven verdicts.
  - Failing any gate → finding `soc2-trail-incomplete` (`severity:
    medium`).
- The check is **about SentinelQA's own audit trail**, not about the
  target's. The intent is to make SentinelQA's own runs admissible as
  evidence in a SOC 2 audit ("our release-confidence engine produces
  this trail per run; here is the artefact").

## Tests required

- `tests/unit/modules/compliance/test_soc2_trail.py` — fixtures: clean
  trail (all 7 pass), tampered trail (line edit), trail with cookie
  leak (gate 7 fires), trail missing module-end record.

## Definition of Done

- [ ] Seven gates ship; each has a named failure mode.
- [ ] `STATUS.md` updated.
