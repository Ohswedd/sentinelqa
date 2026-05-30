# Phase 31 — Browser-Authenticated Audits

## Objective

Today's auth in SentinelQA is API-key + login-form-with-env-var-credentials
(`auth.strategy: test_user`). That covers ~70 % of self-hosted apps but
leaves out the surface the user explicitly asked for: **audits of apps that
sit behind a real human SSO login** — Google / GitHub / Microsoft OAuth,
and the consumer-LLM web surfaces (Claude / ChatGPT / Codex / Gemini /
Mistral Le Chat) where the operator wants to audit their own logged-in
workflows.

This phase ships a Playwright **storage-state-per-target** flow plus the
`sentinel auth login` command for one-time interactive sign-in. The session
state is encrypted at rest and never logged. **Hard constraint** (CLAUDE.md
§6): credentials are entered by the operator into their own browser; SentinelQA
never harvests them, never re-uses them across targets, never bypasses MFA,
never bypasses CAPTCHA. The flow is "the user logs in once, SentinelQA
remembers the session under explicit consent."

## PRD / CLAUDE.md references

- PRD §2 (safety boundary), §10 (testing capabilities), §17 (configuration).
- CLAUDE.md §6 (no stealth / no bypass / no fingerprint evasion), §33 (no
  secret logging), §43 (implementation order — auth comes after the core
  modules are stable).

## Sub-phases & tasks

1. `01-storage-state-vault.md` — `engine/auth/vault.py` encrypted store
   for per-target `storage_state.json` using OS keyring + Fernet fallback.
2. `02-cli-auth-login.md` — `sentinel auth login <name> --url <login-url>
   [--persistent]` interactive flow that opens a headed Chromium, waits
   for the user to complete sign-in, captures `storage_state`, encrypts it
   into the vault.
3. `03-cli-auth-list-revoke.md` — `sentinel auth list`, `sentinel auth
   revoke <name>`, `sentinel auth export <name>` (decrypts only with the
   operator's explicit second confirmation).
4. `04-oauth-helper-profiles.md` — Built-in profiles for the common SSO
   shapes (Google, GitHub, Microsoft) — these are documented launcher
   recipes, NOT credential harvesters. The user signs in normally.
5. `05-llm-web-profiles.md` — Documented profiles + safety guidance for
   Claude.ai, ChatGPT, Codex, Gemini, Le Chat web logins. Same pattern:
   the user signs in; SentinelQA stores the session for replay. Doc
   includes Anthropic / OpenAI / Google ToS notes: auditing **your own
   account** is acceptable; auditing somebody else's is not.
6. `06-runtime-wiring.md` — Runner / discovery / module consumers learn
   to load a storage state when `auth.strategy: browser_session` is set
   and `auth.session_name` resolves in the vault.
7. `07-safety-guards.md` — Refuse to load storage state for a target
   whose host is NOT on the allowlist (re-uses Phase 01 SafetyPolicy);
   refuse to export / decrypt without `--i-acknowledge` flag; audit-log
   every vault operation.
8. `08-tests.md` — Unit (vault crypto, expiry detection), integration
   (Playwright headed-browser smoke gated behind `SENTINELQA_HAS_CHROMIUM=1`),
   safety guards.

## Definition of Done

- A user can `sentinel auth login github.com/myorg` once and run
  `sentinel audit` against an authenticated route afterwards without
  re-typing their credentials.
- Storage state is encrypted at rest (no plaintext cookies on disk).
- No session is ever transmitted off the user's machine by SentinelQA.
- Vault refuses unauthorized targets.
- ADR-0043 (Browser-authenticated audits) accepted.
- PRD §17 documents the `auth.strategy: browser_session` block.

## Phase Gate Review

- [ ] Vault encrypted; OS-keyring fallback works on macOS / Linux / Windows
      docs.
- [ ] CLI flow works end-to-end with the headed Chromium gate.
- [ ] No plaintext cookie or password in `.sentinel/auth/` or logs.
- [ ] Safety: vault refuses non-allowlisted targets.
- [ ] ADR-0043 accepted.
- [ ] PRD updated.
- [ ] `STATUS.md` updated.
