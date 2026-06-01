# ADR-0018: Security module — safe HTTP checks, gated probes, dep + SAST adapters

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

the documentation, §23, §26 require SentinelQA to ship a Safe Security module
that exercises a broad family of web-app security checks:

- response-header hygiene (HSTS, CSP, XFO, XCTO, Referrer-Policy, Permissions-Policy);
- cookie-flag inspection (`HttpOnly`, `Secure`, `SameSite`);
- CORS misconfiguration probes (wildcard ACAO with credentials, reflective ACAO);
- CSRF token presence on state-changing endpoints;
- reflected XSS marker probes (safe; non-executable);
- stored XSS probes (gated; destructive);
- SQL-injection behavioural probes (sandbox-only or destructive + proof);
- IDOR smoke (second-user resource access);
- frontend secrets — JS bundle scanning AND DOM/localStorage inspection;
- dependency scanners — `pip-audit`, `npm audit`, `osv-scanner`;
- optional SAST — `semgrep`.

the engineering guidelines-bearing: there are
no stealth flags, no proxy rotation, no fingerprint evasion. Every
probe goes through `SafetyPolicy.enforce` before it issues a request;
dangerous probes require `security.mode == "authorized_destructive"`
plus a valid proof-of-authorization document.

The (accessibility) and (performance) modules
established the "module + injected runner" pattern (ADR-0016). The
security module is HTTP-driven for most checks, so the "runner" here
is the shared `httpx.Client` plus a token-bucket rate limiter — there
is no per-route Playwright subprocess.

## Decision

We introduce a new module package `modules/security/` and a curated
catalog of stable rule identifiers used by the SARIF writer (Phase
03.05).

1. **Module shape.** `modules.security.SecurityModule` inherits from `engine.modules.base.SentinelModule` and implements the seven-step lifecycle. `execute` runs every enabled check via a shared `CheckContext` carrying the `httpx.Client`, target, `SafetyDecision`, and audit-log path. Each check is a small function returning a `SecurityCheckResult`.
2. **Per-check files.** Each check has its own module under `modules/security/checks/`: - `headers.py` — OWASP-aligned header rule set. - `cookies.py` — cookie attribute parser + auth-cookie heuristic. - `cors.py` — synthetic-origin OPTIONS preflight. - `csrf.py` — form parser + token / `SameSite` heuristic. - `xss_reflected.py` — non-executable marker reflection probe. - `xss_stored.py` — destructive-only stored XSS probe. - `sqli.py` — boolean + time-based behavioural probe, local-only or destructive + proof. - `idor.py` — second-user resource access smoke check. - `frontend_secrets.py` — JS bundle + DOM / storage snapshot scan. - `deps.py` — `pip-audit` / `npm audit` / `osv-scanner` adapters. - `sast.py` — `semgrep` adapter (opt-in).

3. **Safety contract.** Every public `run_*` function in `modules/security/checks/` begins with `SafetyPolicy.enforce(...)` OR with an explicit precondition gate that returns a `skipped=True` result before any I/O. The AST guard in `tests/security/test_module_calls_policy.py` enforces this on every CI run; the forbidden-flag guard in `tests/security/test_security_forbidden_flags.py` enforces the engineering guidelines
4. **Wire models.** `modules/security/models.py` declares the `SecurityIssue` / `SecurityCheckResult` / `SecurityRunOutcome` Pydantic models with `SECURITY_RESULT_SCHEMA_VERSION="1"`. The module writes one `<run-dir>/security/<check>.json` per check plus an `index.json`. Findings carry the per-check artifact path as evidence.
5. **Rule catalog + SARIF.** `modules/security/rules.py` is the single source of truth for stable `SEC-*` rule IDs (e.g. `SEC-HEADERS-HSTS-MISSING`). On import, the module registers every rule with `engine.reporter.sarif_rules.default_sarif_registry`; the Phase-03 SARIF writer reads them by category. Rule IDs are stable across releases — renaming one is a breaking change for any downstream dashboard.
6. **Gated probes.** - **Stored XSS** runs only when `security.mode == "authorized_destructive"` AND `security.checks.xss_stored == true` AND the `target.proof_of_authorization` document is valid for the host and capability. The config validator rejects `security.checks.xss_stored=true` outside destructive mode at load time; the check additionally re-verifies the proof at runtime. - **SQLi** runs only when the target host is local (loopback / RFC1918) OR `security.mode == "authorized_destructive"` with a valid proof. - **Frontend-secrets DOM/storage scan** is opt-in: the check processes snapshots produced by a separate Playwright-side helper if they exist under `<run-dir>/security/snapshots/`. JS bundle scanning is always on when the check itself is enabled. - **SAST (semgrep)** is opt-in via both `security.checks.sast=true` AND `security.dependency_scanners.semgrep=true`. Adapters report `skipped_reason` when the binary is absent — they never auto-install.

7. **IDOR second-user wiring.** The the documentation called for `auth.second_user_*_env`. We landed a structured `auth.second_user` block with `username_env`, `password_env`, `token_env`, and `user_id`. For the release the IDOR check uses `token_env` only (a bearer token is enough to compare resource access); username/password login orchestration is a follow-up. The check skips with an `info` reason rather than fabricating findings when no second-user token is configured.
8. **CLI.** `sentinel security` replaces the Phase-02 stub. Options: `--url`, `--routes`, `--discovery`, `--mode`, `--proof-of-authorization`, `--checks`. Exit codes follow the canonical grid (0/1/2/4/5/6 per the engineering guidelines).
9. **Audit logging.** Every probe writes one entry to `.sentinel/runs/<run-id>/audit.log` via `engine.policy.audit_log.write_audit_entry`. Entries are redacted per the engineering guidelines

## Rationale

- A monolithic security module would couple unrelated checks; small per-check files keep each one independently testable. The `CheckContext` is the only shared surface, and it is immutable.
- A stable rule catalog separate from the SARIF registry lets the module add a curated `recommendation` field that the HTML report and SDK can use — the SARIF descriptor only carries the title / description / helpUri triplet.
- HTTP-only scanning is the right floor for: it works against any framework, depends only on `httpx`, and never requires a browser. The optional snapshot-based DOM / storage scan plugs in a Playwright-side capture for projects that wire it up, without forcing every consumer to run a browser.
- Refusing dangerous probes at the configuration layer (the `_destructive_requires_mode` and `_stored_xss_requires_destructive` validators) AND at runtime (the per-check `_allowed_to_run` gates) is intentional defence-in-depth. Either gate alone has been wrong in other security tools before.

## Consequences

- New rule IDs (`SEC-*`) become public contract; renaming them is a breaking change for downstream consumers (dashboards, ticket templates, GH code-scanning views).
- The security module is now in the per-package coverage gate at ≥ 90%. Per-package coverage is enforced separately from the global 95% floor so the module's HTTP/heuristic surface doesn't pull the global average down. The package's overall coverage is 91 % at landing time, with `xss_stored` and `sast` intentionally below 90 % because their primary paths require a real browser / a real SAST install — those are exercised via the integration suite and the gated tests.
- The `auth.second_user` block becomes a stable config surface; will add the password-grant flow for browsers that require more than a token.
- Stored XSS, SQLi, and SAST are off by default and remain so unless the operator explicitly opts in AND (where applicable) provides a signed proof-of-authorization. This is the law of the build and is enforced both at config load and at probe time.

## Alternatives considered

- **Single monolithic check function.** Rejected — it would couple unrelated checks, hide failure modes, and make the AST policy guard impossible (we'd have one entry-point and many unguarded helpers). Per-check functions give us one trivially-testable surface each.
- **A new `sentinel-ts audit-security` subcommand for everything.** Rejected for the Phase-13 release. The majority of checks (headers, cookies, CORS, CSRF, reflected XSS, SQLi, IDOR, dependency scan) are HTTP-only and require no browser; pushing them through a TS subprocess would add latency, build complexity, and a parallel Pydantic-vs-TypeScript schema surface for no benefit. The browser-required DOM / storage scan reuses an opt-in snapshot file produced by a Playwright helper, which keeps the boundary clean.
- **Inline secrets in YAML for the second-user IDOR check.** Rejected — the engineering guidelines`auth.second_user.token_env` indirection matches the rest of the auth surface.
- **Auto-install `pip-audit` / `semgrep` if missing.** Rejected — the engineering guidelines-installing heavy dependencies. The doctor command reports missing tools; the adapter reports them via `skipped_reason`.
- **Treat stored XSS + SQLi as always-available behind a single `--destructive` flag.** Rejected — each capability has its own toggle so users can pick exactly what they're authorized to run. Defence-in-depth at config and at runtime, not a single switch.

## References

- our product spec Safety Boundary, §10.7 Security, §23 Threat Model, §26 Safe Defaults.
- the engineering guidelines, §9 Module contract, §24 Findings, §26 Security module rules, §33 Logging and secrets, §37 No placeholder completion.
- ADR-0006 Safety policy.
- ADR-0008 Report schemas & reporter pipeline (SARIF rule registry).
- ADR-0015 Module contract and functional module.
- ADR-0016 Accessibility module (runner-Protocol pattern reuse).
