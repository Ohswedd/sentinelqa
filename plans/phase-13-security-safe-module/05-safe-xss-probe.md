# Task 13.05 — Safe XSS probe

## Deliverables

- Reflected XSS probe:
  - For each GET endpoint with query params, submit harmless payloads from a curated list (e.g. `<svg/onload=__SENTINELQA_XSS__>` — the marker is a unique non-executable string we look for in the response after URL- and HTML-encoding).
  - Pattern: detect if the marker is reflected unescaped in the HTML response (presence of `<svg` literally in the body).
  - Severity high; confidence reduced when CSP would mitigate.
- Stored XSS:
  - Only enabled when `security.mode == "authorized_destructive"` AND proof-of-authorization present.
  - Submits the marker into a form; on a subsequent page-load, scans for reflection.
- Both probes:
  - Rate-limited per `security.max_requests_per_second`.
  - Always log every probe to `audit.log`.
  - Never combine with evasion techniques; transparent User-Agent + test-run header.

## Acceptance criteria

- Reflected-XSS fixture triggers high finding with the offending URL + reflection evidence.
- Stored-XSS probe refuses to run without proof.

## Tests required

- `tests/integration/modules/security/test_xss_reflected.py`.
- `tests/integration/modules/security/test_xss_stored_gated.py`.

## PRD / CLAUDE.md references

- PRD §10.7, §2.
- CLAUDE.md §6, §26.

## Definition of Done

- [ ] Probes implemented with gates.
- [ ] Audit log entries emitted.
- [ ] `STATUS.md` updated.
