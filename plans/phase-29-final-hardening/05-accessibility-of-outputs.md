# Task 29.05 — Accessibility of outputs

## Deliverables

- Self-audit:
  - HTML report passes axe-core (no critical, ≤ 0 high in fixture-generated report).
  - Markdown report renders cleanly in GitHub + GitLab previews.
  - CLI output in human mode uses semantic color + screen-reader-friendly progress (no ANSI-only signals).
- Add a test `tests/integration/release/test_report_self_a11y.py` running our own a11y module on the generated `report.html`.

## Acceptance criteria

- All a11y self-checks green.

## Definition of Done

- [ ] Self-a11y test green.
- [ ] `STATUS.md` updated.
