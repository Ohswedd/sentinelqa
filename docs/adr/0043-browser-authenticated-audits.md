# ADR-0043: Browser-authenticated audits via an encrypted Playwright `storage_state` vault

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

Phase 13 already supports `auth.strategy: test_user`, where the
operator stores a username + password in env vars and a Phase-13 login
fixture re-authenticates on every audit. That covers about 70 % of
self-hosted apps — anything with a plain HTML login form, a fixed test
account, and no MFA. The remaining 30 % is what the user explicitly
asked us to cover next:

- SSO-protected apps (Google OAuth, GitHub OAuth, Microsoft Entra, Okta, custom OIDC). The operator can sign in once with their real identity but the flow is impossible to script reliably without storing the actual credentials — which we refuse to do.
- Consumer LLM web surfaces (Claude.ai, ChatGPT, Codex, Gemini, Le Chat) where the operator wants to audit a workflow they built themselves: their own Claude Project, their own custom GPT, their own Gemini extension. Same constraint — the auth flow is rich and changing, and credentials must stay in the operator's hands.

our engineering rules
bypass, and CAPTCHA bypass. our engineering rules
goal is "the user signs in once in their own browser; SentinelQA
remembers the _session_, never the credentials." The user controls
when to revoke, when to expire, and where the encrypted blob lives.

## Decision

Adopt **Playwright's `storage_state` model** as the unit of stored
auth. Operators capture it through a new interactive CLI:

```bash
sentinel auth login github-myorg --url https://github.com/login
```

The CLI opens a headed Chromium (or Firefox / WebKit), the operator
signs in normally — including MFA and CAPTCHA, which SentinelQA never
sees — and on completion SentinelQA captures `context.storage_state()`
and encrypts it into the per-user vault at
`~/.sentinel/auth/<host-slug>/<name>.json.enc`.

### Cryptography

- **AES-256-GCM** via the existing PyCA `cryptography` dep (ADR-0042 already pinned it). Each entry carries its own 12-byte nonce; the associated-data field encodes `<schema-version>:<host>:<name>` so swapping a ciphertext between entries fails the AEAD tag check.
- **Master key in the OS keyring** (`keyring` library, Apache 2.0) under the service `sentinelqa-vault`, account `default`. The library is an optional import — when the keyring is unreachable (headless Linux without dbus, locked-down CI), we fall back to a PBKDF2-SHA256 derivation of a passphrase the operator supplies via the `SENTINEL_VAULT_PASSPHRASE` env var. 600 000 iterations (NIST SP 800-132 / OWASP 2026); configurable upward via env var, never downward.
- Vault files are written with mode `0600`. The per-host directories are `0700`. A redacted metadata sidecar (`<name>.json.meta`) carries the public fields (host, name, timestamps, cookie / local-storage counts) so `sentinel auth list` does NOT need to decrypt the entry.

### Runtime wiring

- New config branch: `auth.strategy: browser_session` plus `auth.session_name: <name>`. The host is taken from `target.base_url`. A Pydantic `model_validator` rejects inconsistent combinations.
- The Phase-08 orchestrator materializes the vault entry into `<run-dir>/auth/storage_state.json` (chmod `0600`), passes the path in the run-config envelope as `storage_state_path`, and deletes the file on teardown regardless of run outcome (try/finally). The plaintext file MUST NOT outlive the run.
- The TypeScript runner extends its `RunConfigSchema` with the same `storage_state_path` field, exports `SENTINELQA_STORAGE_STATE` to child Playwright processes, and ships a new `getSentinelStorageStateUse()` helper the user's `playwright.config.ts` can spread into the `use` block. A `--storage-state
<path>` CLI flag overrides the run-config value.
- The Phase-05 crawler accepts a pre-loaded cookies dict via the existing `extra_cookies` argument — when the strategy is `browser_session`, `sentinel discover` reads the vault in-memory (never to disk), filters cookies to the target host, and passes them in.
- Plugins must declare a new scoped permission, `auth.read:<host>`, before they can call `ctx.auth_session(host, name)`. Cross-host reads are refused at the runtime boundary.

### Safety guards

1. `Vault.get()` refuses any entry whose recorded host is not in the active target's allowlist — a `VaultHostMismatchError` (`E-AUTH-003`) is raised; the run aborts at exit 4.
2. Expired entries raise `VaultEntryExpiredError` (`E-AUTH-002`). The vault never extends or refreshes a session.
3. AEAD failures (tampered ciphertext, wrong key) raise `VaultIntegrityError` (`E-AUTH-004`).
4. The login flow refuses to capture if the post-login URL host differs from the start URL host AND is not on the allowlist (`LoginOriginChangedError`, `E-AUTH-005`) — defense against phishing redirects.
5. `--ci` mode rejects every interactive command (`AuthCommandForbiddenInCiError`, `E-AUTH-006`).
6. The `engine.policy.redaction` value-level rules add a `Cookie:` / `Set-Cookie:` header pattern; the key-name set now includes `cookies`, `localStorage`, `local_storage`, `storage_state`, `storage_state_json` so any accidental log of those fields is replaced with a `[REDACTED:…]` marker.
7. An AST guard in `tests/security/test_no_credentials_in_profiles.py` fails the build if a future profile field name matches `password|secret|token|key|credential|otp`. Auth profiles are documentation, not credential carriers.

### Built-in profiles

Three OAuth profiles (Google, GitHub, Microsoft Entra) and five
LLM-web profiles (Claude.ai, ChatGPT web, ChatGPT Codex, Google
Gemini, Mistral Le Chat). Each profile carries: login URL, success
URL patterns the login flow watches to auto-detect completion, an
MFA hint, the provider's Terms-of-Service URL, and a category
(`oauth` or `llm-web`). Profiles are pure metadata — no fields that
even look like credentials.

## Consequences

- **Positive:** SentinelQA can now audit ~95 % of real-world apps (the existing 70 % plus the SSO and personal-LLM-workflow 25 %). The operator's password / OTP / OAuth bearer token never touches SentinelQA. The encrypted vault makes "ship a teammate the session for an offline audit" a documented, auditable workflow with an explicit `--i-acknowledge` flag.
- **Positive:** The vault sits behind a single Python boundary (`engine.auth.Vault`); the TS runner only receives a path. Future remote-execution surfaces (Phase 35+) can stream the storage-state over the same path-based contract without re-deriving the cryptography.
- **Negative / trade-off:** We add the `keyring` library as a soft dependency. When it isn't usable, the operator MUST set a strong passphrase via env var; we refuse to fall back to an unencrypted blob. That's a friction cost on locked-down CI runners.
- **Negative / trade-off:** Storage states expire. We default the TTL to 24 h so a forgotten capture cannot keep an audit running against a stale session indefinitely; operators must re-run `sentinel auth
login` when an audit fails with `E-AUTH-002`. We accept the friction — silent extension would be a safety regression.
- **Follow-up obligations:** Phase 35 (public release engineering) will need to surface the vault's PBKDF2-iteration knob in the docs site and pin the `keyring` library at a version that ships Apple-Keychain / Secret-Service / Windows-Credential-Manager backends out of the box. Tracked in `docs/dev/auth-internals.md`.

## Alternatives considered

- **Plaintext storage_state on disk.** Rejected outright — the file carries session cookies and effectively grants login. our engineering rules forbids it.
- **Re-implement the SSO flow ourselves.** Rejected — implementing Google / GitHub / Microsoft OAuth state machines means owning their brittle redirect chains forever AND inevitably touching credentials (the resource-owner-password-credentials flow is the only way, and every major provider deprecates or restricts it). The user-driven browser flow side-steps the whole class.
- **Ship a SentinelQA-managed browser extension.** Rejected — cross-browser extension distribution adds two new build pipelines, three review processes, and a per-vendor signing dependency for a feature the headed-browser flow already covers.
- **Stash the master key in a config file under `~/.sentinel`.** Rejected — that just moves the encryption-at-rest problem one level. The OS keyring is the only place we can rely on a user-attested decrypt action.

## References

- PRD section(s): our product spec (Safety Boundary), our product spec (Testing Capabilities), our product spec (Configuration).
- our engineering rules rule(s): our engineering rules(Non-negotiable safety boundary), our engineering rules(Logging and Secrets), our engineering rules(Implementation Order — auth lands after the core engine is stable).
- External: [Playwright `storage_state` docs](https://playwright.dev/docs/auth), [PyCA cryptography AES-GCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM), [NIST SP 800-132 (PBKDF2)](https://csrc.nist.gov/publications/detail/sp/800-132/final), [Python keyring library](https://pypi.org/project/keyring/).
- Related ADRs: ADR-0006 (Safety policy), ADR-0018 (Security module), ADR-0029 (Plugin architecture).
