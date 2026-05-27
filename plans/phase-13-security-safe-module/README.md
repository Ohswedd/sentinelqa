# Phase 13 — Security (Safe) Module

## Objective

Implement the **Safe Security** module (PRD §10.7, §23, §26): non-destructive checks for headers, cookies, CORS, CSRF, safe XSS/SQLi probes only in sandbox/local, IDOR smoke, secret-scan integration, dependency-scan integration, and SARIF export. Default destructive mode OFF; allowlist enforced.

Per CLAUDE §6/§26, this module is the front line of the safety boundary. It must refuse to run against unauthorized targets and never include exploit weaponization.

## PRD / CLAUDE.md references

- PRD §2 Safety boundary, §10.7 Security, §23 Threat model, §26 (Safe defaults).
- CLAUDE.md §6, §9, §26.

## Sub-phases & tasks

1. `01-module-skeleton.md` — `SecurityModule`.
2. `02-headers-check.md` — Security headers.
3. `03-cookie-flags.md` — `HttpOnly`, `Secure`, `SameSite`.
4. `04-cors-csrf.md` — CORS misconfig, CSRF token presence.
5. `05-safe-xss-probe.md` — Reflected XSS safe probe; sandbox-only stored XSS.
6. `06-safe-sqli-probe.md` — SQLi safe probe; sandbox-only.
7. `07-idor-smoke.md` — IDOR smoke checks across auth roles.
8. `08-frontend-secrets.md` — Secrets in JS bundle / DOM / localStorage / network.
9. `09-deps-and-sast.md` — Dependency-scan adapter (`pip-audit`, `npm audit`, `osv-scanner`) + SAST adapter (`semgrep` optional).
10. `10-sarif-export.md` — SARIF rule registration (uses Phase 03 writer).
11. `11-policy-enforcement.md` — Re-enforce safety policy at every step.
12. `12-security-cli.md` — `sentinel security` command.
13. `13-tests.md` — sweep, including refusal tests against public targets without proof.

## Definition of Done

- All safe checks implemented; default safe.
- Refusal to scan public, non-allowlisted targets verified by test.
- SARIF output validates and uploads via GitHub Code Scanning (verified in Phase 17).
- Destructive checks gated by proof-of-authorization (Phase 01 §1.3) and explicit config.

## Phase Gate Review

- [ ] Every check produces actionable findings (CLAUDE §24 — specific, not vague).
- [ ] Safety refusal tests pass.
- [ ] SARIF validates.
- [ ] Dep scan integrated; output normalized to `Finding`.
- [ ] ADR-0014 (Security policy implementation) committed.
- [ ] `STATUS.md` updated.
