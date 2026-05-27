# Phase 11 — Accessibility Module

## Objective

Implement the **Accessibility** module (PRD §10.4, §28): run `axe-core` per route, plus keyboard navigation, focus order, ARIA, contrast, modal trap, landmark, and screen-reader-name checks. Findings normalized into the standard `Finding` schema.

Per CLAUDE §28: NEVER claim "fully WCAG compliant" — always describe outputs as "automated accessibility checks".

## PRD / CLAUDE.md references

- PRD §10.4 Accessibility, §32 Build order.
- CLAUDE.md §9 Module contract, §28 Accessibility rules.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `AccessibilityModule` (CLAUDE §9 shape).
2. `02-axe-integration.md` — Inject `axe-core` into pages via TS helper; pull violations.
3. `03-keyboard-focus-checks.md` — Tab order, focus visibility, modal trap.
4. `04-contrast-and-landmarks.md` — Color contrast (via axe), landmark structure, screen-reader names.
5. `05-findings-normalization.md` — Map axe rules → Sentinel categories with severity, evidence, and remediation.
6. `06-a11y-cli.md` — `sentinel a11y` command.
7. `07-tests.md` — sweep.

## Definition of Done

- Module produces findings against the fixture with both compliant and non-compliant pages.
- Output language never claims full WCAG compliance.
- All severities mapped consistently.

## Phase Gate Review

- [ ] Axe integration verified on fixture.
- [ ] Keyboard + focus checks pass on compliant fixture and fail on non-compliant fixture.
- [ ] Output text reviewed against CLAUDE §28 — no "fully WCAG compliant" claims.
- [ ] `STATUS.md` updated.
