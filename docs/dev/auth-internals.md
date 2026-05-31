# Auth vault internals

> Status: **Stable** (Phase 31, ADR-0043).

This page is the contributor-facing reference for the encrypted vault
backing `auth.strategy: browser_session`. The user-facing tour lives at
[`docs/user/auth-flows.md`](../user/auth-flows.md).

---

## On-disk layout

```
~/.sentinel/auth/
├── .salt                                  # 16-byte PBKDF2 salt (passphrase fallback only)
├── github.com/
│   ├── myorg.json.enc                     # AES-256-GCM ciphertext (0600)
│   └── myorg.json.meta                    # Redacted metadata sidecar (0600)
├── staging.example.com/
│   ├── ci.json.enc
│   └── ci.json.meta
└── audit.log                              # Append-only JSONL of vault operations
```

The per-host directories are `0700`. Override the root with
`SENTINEL_VAULT_ROOT=<dir>` (tests use this; never set it in
production).

### Encrypted envelope

Each `.json.enc` file is `nonce || ciphertext || tag`, where the
ciphertext and tag are produced by `AESGCM.encrypt`. The plaintext
envelope is:

```json
{
  "schema_version": "1.0.0",
  "name": "<entry-name>",
  "host": "<recorded-host>",
  "storage_state_json": "<Playwright storage_state as a JSON string>",
  "created_at": "<ISO 8601 UTC>",
  "expires_at": "<ISO 8601 UTC>",
  "last_used_at": "<ISO 8601 UTC | null>",
  "cookies_count": <int>,
  "local_storage_keys": <int>,
  "captured_by": "cli"
}
```

The associated-data field of the AEAD is
`<schema_version>:<host>:<name>`. Swapping a `.json.enc` from
`a.com/foo` into `b.com/foo` fails the tag check.

### Metadata sidecar

`<name>.json.meta` is plain JSON of the public fields (host, name,
timestamps, cookie + local-storage counts). It exists so
`sentinel auth list` can produce a redacted view without decrypting
anything. The vault never trusts the sidecar — every other API
(`get`, `export`) reads the ciphertext.

---

## Master key

The 32-byte AES-256-GCM master key has two acquisition paths:

1. **OS keyring** (preferred). Stored under service
   `sentinelqa-vault`, account `default`. The `keyring` library
   (Apache 2.0) is an optional import; we never silently degrade.
   Backends:

   - macOS: login Keychain
   - Linux: Secret Service (gnome-keyring / kwallet)
   - Windows: Credential Manager

2. **PBKDF2 passphrase fallback.** When the keyring is unreachable
   (headless Linux without dbus, locked-down CI), we derive the key
   from a passphrase via PBKDF2-SHA256:
   - Salt: 16 random bytes, stored at `~/.sentinel/auth/.salt`.
   - Iterations: 600 000 (NIST SP 800-132 / OWASP 2026).
     `SENTINEL_VAULT_PBKDF2_ITERATIONS` can raise this, never lower.
   - Passphrase: read from `SENTINEL_VAULT_PASSPHRASE`.

`MasterKey` zeros its internal bytearray on `close()` using a
`ctypes.memset` (best-effort; Python's GC may have copied the bytes,
but we make the in-memory copy go away as soon as the operation
finishes).

---

## Safety guards

All raised as `engine.errors.base.AuthError` subclasses; all map to
`exit_code = 4` (unsafe target) except the not-found / CI-rejection
cases (exit 2):

| Code         | Raised when                                        | Exit |
| ------------ | -------------------------------------------------- | ---- |
| `E-AUTH-001` | Vault has no entry for `(host, name)`              | 2    |
| `E-AUTH-002` | Entry's `expires_at` is in the past                | 4    |
| `E-AUTH-003` | Stored host not in active target's `allowed_hosts` | 4    |
| `E-AUTH-004` | AEAD tag failed (tampering, wrong key)             | 4    |
| `E-AUTH-005` | Login flow landed on a non-allowlisted host        | 4    |
| `E-AUTH-006` | Interactive `sentinel auth …` invoked in CI mode   | 2    |

In addition, the redactor's value-level rules now match `Cookie:` /
`Set-Cookie:` header lines, and its key-name set includes
`cookies`, `localStorage`, `local_storage`, `storage_state`,
`storage_state_json`. Any accidental log of those fields is
replaced with `[REDACTED:<category>]`.

The AST guard at
`tests/security/test_no_credentials_in_profiles.py` rejects any field
in `engine/auth/profiles/` whose name matches
`password|secret|token|key|credential|otp`. Auth profiles are
documentation, not credential carriers.

---

## Runtime contract

`sentinel test` (and any future module that drives the Playwright
runner) calls
`engine.auth.runtime.materialize_storage_state(...)` to decrypt the
entry into `<run-dir>/auth/storage_state.json` (chmod `0600`). The
path is passed through the run-config as `storage_state_path` and the
TS runner exports it as the env var `SENTINELQA_STORAGE_STATE`.
Generated tests (or the user's `playwright.config.ts`) call
`getSentinelStorageStateUse()` from `@sentinelqa/ts-runtime/playwright`
to spread `{storageState: <path>}` into Playwright's `use` block.

`sentinel discover` calls `load_storage_state_dict(...)` so cookies
flow into the `httpx.Client` via the existing
`Crawler.crawl(extra_cookies=...)` argument — the plaintext storage
state never hits disk during discovery.

Both code paths emit one audit-log entry per use:

```json
{
  "event": "auth.session_used",
  "host": "<host>",
  "name": "<name>",
  "cookies_count": <int>,
  "age_seconds": <float>
}
```

Cookie values and local-storage payloads never appear in audit-log
records — `engine.policy.audit_log.write_audit_entry` runs the
redactor before flushing.

The materialized plaintext file is deleted on teardown by a
`try/finally` block in the runner caller, even if the run crashes.
`tests/security/test_session_tmpfile_lifetime.py` enforces the
invariant.

---

## Plugin permission

Plugins must declare a scoped `auth.read:<host>` permission in their
manifest before they can call `ctx.auth_session(host, name)`. The
loader rejects manifests with unscoped `auth.read` — every plugin
declares exactly which host it intends to read sessions for, and
cross-host reads are refused at the runtime boundary.

---

## Testing

- Unit: `tests/unit/auth/`
- Integration: `tests/integration/auth/`,
  `tests/integration/cli/test_auth_command.py`,
  `tests/integration/plugins/test_auth_permission_required.py`
- Security: `tests/security/test_no_credentials_in_profiles.py`,
  `tests/security/test_audit_log_never_carries_cookies.py`,
  `tests/security/test_vault_host_match.py`,
  `tests/security/test_login_origin_change.py`,
  `tests/security/test_session_tmpfile_lifetime.py`
- Config schema: `tests/unit/config/test_auth_browser_session.py`

The Chromium-driven end-to-end gate is held by the broader
`SENTINELQA_HAS_CHROMIUM=1` lane (same as the existing Playwright
integration tests). The Phase-31 unit suite stubs the browser
launcher so it runs everywhere — including CI without a browser
install.
