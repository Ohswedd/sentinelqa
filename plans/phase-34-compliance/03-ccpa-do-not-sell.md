# Task 34.03 — CCPA "Do Not Sell or Share" link check

## Deliverables

- `modules/compliance/ccpa.py`:
  - On every page the Phase 05 crawler discovers, look for the CCPA
    "Do Not Sell or Share My Personal Information" link. Heuristics:
    link text matching `(do not sell|do not share|opt out|privacy
    choices)` case-insensitive; `href` to a page containing the
    word `sell` / `share` / `opt-out`.
  - For pages that lack the link, finding
    `ccpa-do-not-sell-link-missing` (`severity: medium` if the site
    serves US-shaped audiences, configurable).
  - For pages where the link exists, follow it once and assert the
    target page actually exposes the opt-out form (not a generic
    privacy policy).

## Tests required

- `tests/unit/modules/compliance/test_ccpa_link_detect.py` —
  fixtures with + without link.
- `tests/integration/modules/compliance/test_ccpa_follow.py` — stub
  server that links to a 200 privacy policy without an opt-out form
  → finding fires.

## Definition of Done

- [ ] Link detection is conservative (heuristics, not a NLP model).
- [ ] Wording does NOT claim "you are CCPA compliant".
- [ ] `STATUS.md` updated.
