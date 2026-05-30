# Task 31.07 — Safety guards (no harvest, no replay against new hosts, no leak)

## Deliverables

- `engine/auth/vault.py::Vault.get()` refuses to return a session whose
  recorded host does not match the active target's allowed_hosts set
  (CLAUDE.md §6 — re-uses `engine.safety.policy.SafetyPolicy`). Raises
  `UnsafeTargetError`.
- `Vault.get()` refuses expired entries; the run aborts with
  `E-AUTH-002` (added to `engine/errors/codes.py`).
- The login flow refuses to capture state if the post-login URL is on
  a different origin than the start URL (e.g. an unexpected redirect
  to a phishing page).
- `engine/policy/redaction.py` extended with two new rules:
  - Cookie values longer than 16 chars (real session cookies usually
    are) get redacted with category `cookie` regardless of header
    context.
  - Local-storage payloads in any logged dict are redacted.
- Audit log scrub: ensure cookie / storage-state values can NEVER
  appear in `audit.log`. New unit test
  `tests/security/test_audit_log_never_carries_cookies.py` simulates
  a session-use audit-log write and asserts the redactor caught it.
- Plugin loader (`engine.plugins.loader`) gains a NEW required
  permission `auth.read:<host>` — plugins must declare which hosts'
  sessions they want before they can decrypt vault entries. Missing
  declaration is a load-time rejection (existing capability-allowlist
  pattern).

## Tests required

- `tests/security/test_vault_host_match.py` — vault refuses to return
  a session for a host outside `target.allowed_hosts`.
- `tests/security/test_login_origin_change.py` — login flow refuses
  to capture after a cross-origin redirect.
- `tests/security/test_audit_log_never_carries_cookies.py` — see
  above.
- `tests/integration/plugins/test_auth_permission_required.py` —
  plugin without `auth.read:<host>` is rejected.

## Definition of Done

- [ ] All four safety guards green under tests.
- [ ] `tests/security/` covers every leak vector.
- [ ] Audit-log + reports cannot ever leak a session cookie.
- [ ] `STATUS.md` updated.
