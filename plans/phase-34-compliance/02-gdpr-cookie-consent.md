# Task 34.02 — GDPR cookie consent

## Deliverables

- `modules/compliance/gdpr.py`:
  - Detect cookie-consent banner on first page-load (heuristics:
    `aria-label` / `id` / `class` containing `cookie`/`consent`/`gdpr`;
    role=`dialog`; presence of accept/reject buttons).
  - Capture `Set-Cookie` headers from the **first** page load (before
    the user interacts with the banner). Non-essential cookies set
    before consent → finding `gdpr-cookies-before-consent` (`severity:
    high`).
  - Detect "accept all" / "reject all" symmetry — both must be a
    single click (EDPB guidance 03/2022). Asymmetric reject UX →
    finding `gdpr-asymmetric-consent` (`severity: medium`).
  - Findings carry `compliance_id: gdpr:Art.6` / `gdpr:EDPB-03/2022`.

## Tests required

- `tests/unit/modules/compliance/test_gdpr_banner_detect.py` —
  fixtures with + without consent banners.
- `tests/integration/modules/compliance/test_gdpr_e2e.py` — Phase 26
  `nextjs` example doesn't have a banner (deliberately); check fires.

## Definition of Done

- [ ] Findings use "automated check found", not "your site is not
      GDPR compliant".
- [ ] `STATUS.md` updated.
