# Task 13.02 — Security headers

## Deliverables

- For each discovered route, evaluate response headers against an audited list:
  - `Strict-Transport-Security`
  - `Content-Security-Policy` (validate basic structure; warn on `unsafe-inline`).
  - `X-Frame-Options` or CSP `frame-ancestors`.
  - `X-Content-Type-Options: nosniff`.
  - `Referrer-Policy`.
  - `Permissions-Policy` (warn if absent).
- Each missing/misconfigured header → finding with severity per OWASP guidance:
  - HSTS missing on HTTPS site → high.
  - CSP missing → high if app handles user input.
  - X-Content-Type-Options missing → medium.
  - Referrer-Policy missing → low.
- Findings include exact route, observed header value (redacted), expected value, OWASP reference URL.

## Acceptance criteria

- Fixture serving no security headers triggers the expected severities.
- Fixture with full headers produces 0 findings.

## Tests required

- `tests/integration/modules/security/test_headers.py`.

## PRD / CLAUDE.md references

- PRD §10.7.
- CLAUDE.md §26.

## Definition of Done

- [ ] Header checks implemented.
- [ ] Severity mapping documented.
- [ ] `STATUS.md` updated.
