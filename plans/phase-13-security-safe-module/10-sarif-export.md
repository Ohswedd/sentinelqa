# Task 13.10 — SARIF rule registration

## Deliverables

- Every security check registers its rule in `engine/reporter/sarif_rules.py` (Phase 03 §5) with:
  - `id` (e.g. `SEC-HEADERS-HSTS-MISSING`).
  - Short title.
  - Full description.
  - `helpUri` pointing at our docs (Phase 27).
- The reporter automatically includes these rules in `sarif.json` when the module runs.

## Acceptance criteria

- SARIF output contains every triggered rule with metadata.
- GitHub Code Scanning upload accepts the file (smoke verified in Phase 17).

## Tests required

- `tests/integration/reporter/test_sarif_security_rules.py`.

## PRD / CLAUDE.md references

- PRD §10.7, §21.
- CLAUDE.md §26, §38.

## Definition of Done

- [ ] Rules registered + tested.
- [ ] `STATUS.md` updated.
