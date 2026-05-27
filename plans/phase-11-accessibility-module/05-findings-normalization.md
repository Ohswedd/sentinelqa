# Task 11.05 — Findings normalization

## Deliverables

- `modules/accessibility/findings.py` mapping axe rule IDs → `Finding` schema:
  - `id`: `A11Y-<rule-id>-<short-hash>`.
  - `category`: `accessibility`.
  - `severity`: from axe impact (`critical|serious|moderate|minor` → `high|high|medium|low`).
  - `confidence`: derived per rule (axe rules with `experimental` get lower confidence).
  - `recommendation`: actionable remediation text (curated dictionary per rule).
  - `evidence`: screenshot of the offending element + DOM snippet.
  - Language never claims WCAG compliance — instead "Automated accessibility check found:".

## Acceptance criteria

- Findings adhere to PRD §18.2 schema.
- Severity mapping verified by tests.

## Tests required

- `tests/unit/modules/accessibility/test_findings.py`.

## PRD / CLAUDE.md references

- PRD §10.4, §18.2, §20.
- CLAUDE.md §24, §28.

## Definition of Done

- [ ] Mapping committed; severities tested.
- [ ] No "WCAG compliant" string anywhere in module output.
- [ ] `STATUS.md` updated.
