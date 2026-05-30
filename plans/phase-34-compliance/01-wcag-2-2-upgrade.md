# Task 34.01 — WCAG 2.2 upgrade

## Deliverables

- Phase 11's `modules.accessibility` defaults `axe.tags = ["wcag2a",
  "wcag2aa", "wcag21a", "wcag21aa"]`. Add the new 2.2 SCs:
  `wcag22a`, `wcag22aa` (axe-core 4.10+ supports them).
- Add deterministic checks (no axe required) for the 2.2 criteria
  axe doesn't yet cover well:
  - **2.4.11 Focus Not Obscured (Minimum)** — for each focusable
    element, screenshot the focused state; assert the bounding box
    is not occluded by sticky / fixed elements.
  - **2.5.7 Dragging Movements** — flag UI elements styled with
    `cursor: grab` / `draggable=true` that have no keyboard alternative.
  - **2.5.8 Target Size (Minimum)** — flag clickable elements with
    bounding box < 24×24 CSS px (and no exception applies).
  - **3.3.7 Redundant Entry** — heuristic: forms that ask for the
    same info twice within one flow.
  - **3.3.8 Accessible Authentication (Minimum)** — flag login
    flows that require cognitive function tests (CAPTCHA puzzles)
    with no alternative.
- Findings carry `compliance_id: wcag-2.2:<sc-number>`.

## Tests required

- `tests/unit/modules/accessibility/test_wcag22_focus_obscured.py` —
  fixture page with a sticky header that obscures focus.
- `tests/unit/modules/accessibility/test_wcag22_target_size.py` —
  fixture button at 20×20 px → finding fires.

## Definition of Done

- [ ] New SCs ship.
- [ ] No wording claims compliance (lint guard re-uses Phase 11's
      `tests/security/test_no_wcag_compliance_claims.py`).
- [ ] `STATUS.md` updated.
