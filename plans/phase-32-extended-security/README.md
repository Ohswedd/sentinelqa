# Phase 32 — Extended Security Skill Catalog

## Objective

The Phase 13 security module covers the OWASP basics (headers, cookies,
CORS, CSRF, safe XSS, IDOR smoke, secret scan, SARIF export). Phase 32
expands the catalog with nine **defensive / assessment** checks drawn from
the Anthropic Cybersecurity Skills taxonomy plus our existing PRD §10.7
follow-ups. Every check stays inside the CLAUDE.md §6 boundary — no
offensive exploitation, no WAF bypass, no aggressive fuzzing. Each check
maps to a CWE / OWASP-API-Top-10 / ATT&CK id where applicable, so findings
become standards-anchored rather than internal-jargon.

## PRD / CLAUDE.md references

- PRD §10.7 (Security testing), §10.9 (LLM-code-specific audits), §13
  (CLI), §17 (Configuration), §18 (Finding schema).
- CLAUDE.md §6 (forbidden capabilities), §26 (Security module rules).
- Anthropic Cybersecurity Skills repo — used as a taxonomy / naming
  source, NOT as code to vendor in (offensive material excluded; see
  research note in `docs/release/safety-audit-2026-05-30.md`).

## Sub-phases & tasks

1. `01-jwt-weakness-scanner.md` — Parse `Authorization` + cookies; flag
   `alg=none`, HS256-with-weak-secret, missing `exp`/`aud`/`iss`. CWE-347.
2. `02-cookie-security-extended.md` — Phase 13's cookie checker upgraded
   to detect missing `__Host-` prefix, missing `SameSite`, and mis-set
   `Domain`/`Path` scopes.
3. `03-tls-cert-posture.md` — Read-only TLS handshake against the
   allowlisted host: cipher suite, TLS version, cert chain SHA-256,
   HSTS / `Strict-Transport-Security` / preload status. No
   downgrade attacks, no cipher brute-forcing.
4. `04-graphql-safety-probe.md` — Detect introspection-on-in-prod, depth
   limit absent, complexity unbounded, missing auth on mutations. CWE-770.
5. `05-owasp-api-top10-bola-idor.md` — Replay observed API calls under a
   **second seeded test identity** (`auth.second_user` block; explicit
   destructive mode). Flag if data for identity A is reachable as B.
   OWASP-API-2023-01 (BOLA), API-2023-03 (BFLA).
6. `06-frontend-only-auth-deeper.md` — Phase 19's LLM-audit "frontend-only
   auth" gets a deeper probe: enumerate XHRs the gated page makes,
   replay each one anonymously, assert 401/403. CWE-862.
7. `07-secret-in-bundle-scanner.md` — Fetch every JS bundle Playwright
   loads; regex for AWS / GCP / Azure / Stripe / Slack / GitHub / private
   keys. Reports the bundle URL + line + redacted prefix.
8. `08-ssrf-open-redirect-map.md` — For inputs that accept URLs (forms /
   query params discovered by Phase 05), assert the server rejects
   `127.0.0.1`, `169.254.169.254`, `file://`, internal CIDRs, and that
   redirect endpoints can't be tricked into `//evil.example.com`. CWE-918
   / CWE-601.
9. `09-cwe-attack-mapping.md` — Every existing finding category in the
   security module gains a `cwe_id` + (where applicable) `attack_id`
   tag. The reporter surfaces them; SARIF output uses the standard
   `taxa` extension to reference them.

## Definition of Done

- Each check ships as a `modules.security.checks.<name>` module behind
  Phase 13's existing `SecurityCheck` Protocol.
- Each check has a CWE id in its findings; SARIF output references the
  `cwe.mitre.org` taxa.
- Findings re-use Phase 03's evidence requirement; medium+ severity
  must carry evidence.
- ADR-0044 (Extended security skill catalog) accepted.
- PRD §10.7 expanded with §10.7.1 (Extended catalog).
- `tests/security/test_no_offensive_checks.py` greps the new modules
  for forbidden patterns (`exploit`, `bypass`, `evade`, raw shellcode,
  XSS payload that does anything beyond reflect-and-detect).

## Phase Gate Review

- [ ] Nine new checks green under unit + integration tests.
- [ ] No offensive payload anywhere in the new code.
- [ ] CWE / ATT&CK ids in every new finding.
- [ ] SARIF output validates against the official schema with the new
      `taxa` entries.
- [ ] ADR-0044 accepted.
- [ ] PRD updated.
- [ ] `STATUS.md` updated.
