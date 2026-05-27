# Task 11.04 — Contrast, landmarks, screen-reader names

## Deliverables

- Use `axe-core` for contrast (default), augmented with a small fallback that catches dynamic colors axe might miss.
- Landmark structure: ensure `<header>`, `<nav>`, `<main>`, `<footer>` or equivalent ARIA landmarks exist on routes that are full pages.
- Screen-reader-name check: every interactive element returns a non-empty accessible name (via Playwright's `getAttribute('aria-label')` fallback chain or computed AX name).

## Acceptance criteria

- Fixture without `<main>` landmark → finding.
- Icon-only button without `aria-label` → finding.

## Tests required

- `tests/integration/modules/accessibility/test_landmarks.py`.
- `tests/integration/modules/accessibility/test_sr_names.py`.

## PRD / CLAUDE.md references

- PRD §10.4.
- CLAUDE.md §28.

## Definition of Done

- [ ] Checks implemented and tested.
- [ ] `STATUS.md` updated.
