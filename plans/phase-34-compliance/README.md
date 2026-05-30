# Phase 34 — Compliance Packs

## Objective

Per CLAUDE.md §28, SentinelQA must NOT claim WCAG / GDPR / CCPA / SOC 2
compliance — only that automated checks for known compliance signals
pass. Phase 34 ships **packs** of automated checks for the four most
asked-for regimes. The same wording rule applies to every output: the
report says "Automated WCAG-2.2 checks found …" never "your app is WCAG
2.2 compliant".

## PRD / CLAUDE.md references

- PRD §10.4 (Accessibility), §10.7 (Security), §10.9 (LLM audit),
  §17 (Configuration), §32 (Build order — compliance comes after the
  core modules stabilise).
- CLAUDE.md §28 (Accessibility wording rule applies to compliance
  outputs too), §32 (Error handling — typed compliance failures), §38
  (Report rules — answers questions).

## Sub-phases & tasks

1. `01-wcag-2-2-upgrade.md` — Phase 11's axe-core ruleset is
   `wcag21aa`. Add the new 2.2 success criteria (focus appearance,
   accessible authentication, dragging movements, target size, …).
2. `02-gdpr-cookie-consent.md` — Detect cookie-consent banners; flag
   non-essential cookies set before consent; check `Set-Cookie` order
   against EU "cookie wall" rules.
3. `03-ccpa-do-not-sell.md` — Detect the "Do Not Sell or Share My
   Personal Information" link required for US residents; check that
   the linked page actually exposes an opt-out.
4. `04-soc2-trail.md` — Audit that every SentinelQA run produces a
   complete, redacted, append-only `audit.log` (already a Phase 02
   guarantee — this task adds a quality gate that the auditor can
   point at).
5. `05-policy-dsl.md` — Lightweight compliance-pack DSL so users can
   compose their own packs (e.g. "HIPAA shape" = a mix of existing
   security + GDPR + SOC2 checks with thresholds).

## Definition of Done

- Four ready-to-use packs ship under `policy/compliance/`.
- No pack claims "compliant"; every pack output uses "automated check
  found" / "automated check passed" / "manual review recommended".
- Findings carry compliance-regime tags (`gdpr:cookies-before-consent`,
  `wcag-2.2:target-size`, etc.).
- ADR-0046 (Compliance packs) accepted.
- PRD §10.4.1 + §17 updated.

## Phase Gate Review

- [ ] Four packs ship.
- [ ] No "we are compliant" language anywhere in pack output.
- [ ] Pack DSL parses + validates.
- [ ] ADR-0046 accepted.
- [ ] `STATUS.md` updated.
