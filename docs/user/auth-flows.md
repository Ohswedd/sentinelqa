# Auth flows

> Status: **Stable** (, ADR-0043).

SentinelQA audits applications by sending real HTTP requests to them and
optionally driving them through a real Playwright browser. That means
the audit needs the same kind of session your users have. SentinelQA
supports three top use cases for getting a session into an audit.

In every case, **SentinelQA never sees your username, password, OTP,
or OAuth bearer token.** You sign in yourself, in your own browser;
SentinelQA captures the session that signs you in (cookies + local
storage), encrypts it locally with AES-256-GCM, and replays it on
later audits.

---

## 1. Audit an SSO-protected app

You have a staging app behind Google / GitHub / Microsoft OAuth, or
your own SSO. Run the one-time interactive capture:

```bash
sentinel auth login github-myorg \ --url https://staging.example.com/login \ --profile github-oauth \ --ttl 24
```

The CLI opens a headed Chromium at the login URL. Sign in normally —
including MFA. When the post-login screen appears, press Enter (or, if
you used a `--profile`, the flow auto-detects completion when it lands
on one of the profile's `success_url_patterns`).

In your `sentinel.config.yaml`:

```yaml
target: base_url: https://staging.example.com/ allowed_hosts: - staging.example.com
auth: strategy: browser_session session_name: github-myorg
```

Subsequent `sentinel audit` runs replay the encrypted session
automatically. The plaintext storage state is materialised under
`<run-dir>/auth/storage_state.json` at run start (chmod `0600`) and
deleted on teardown — even if the run crashes — so the cookies never
outlive the audit.

When the session expires (24 h by default), the run aborts with
`E-AUTH-002` and asks you to re-capture. There is no silent extension.

### Cross-origin IdP redirects

If the login flow lands you on a different host (e.g. an Entra IdP at
`login.microsoftonline.com` redirects you back to your staging app),
SentinelQA refuses to capture unless that host is on
`target.allowed_hosts`. The error is `E-AUTH-005`. Add the IdP to
`allowed_hosts` and re-run — the safety guard is doing its job (a
phishing redirect to an unrelated host would otherwise capture an
attacker-controlled session).

---

## 2. Audit a workflow in your own ChatGPT / Claude / Gemini account

The auth-profile catalogue includes five **LLM-web profiles** for the
common consumer LLM apps:

| Profile           | App                        |
| ----------------- | -------------------------- |
| `claude-ai`       | claude.ai                  |
| `chatgpt-web`     | chatgpt.com                |
| `chatgpt-codex`   | chatgpt.com (Codex routes) |
| `google-gemini`   | gemini.google.com          |
| `mistral-le-chat` | chat.mistral.ai            |

The flow is the same as case (1). Capture once:

```bash
sentinel auth login claude-projects \ --url https://claude.ai/login \ --profile claude-ai \ --ttl 12
```

…and point `auth.strategy: browser_session` + the session name in your
config. The use case is **auditing your own logged-in workflows on
your own account** — for example, a Claude Project you built that
handles internal PII, a custom GPT you ship to your team, a Gemini
extension hitting your own Workspace data.

**What this is not.** SentinelQA does not drive the LLM web UI for
content generation, and it does not audit accounts other than yours.
Each provider's Terms of Service is linked from the profile (run
`sentinel auth list-profiles --json` to see them); auditing your own
account is acceptable to all of them, scraping is not, and impersonation
of other users is never appropriate.

---

## 3. Share a vault entry with a teammate

The encrypted vault lives under `~/.sentinel/auth/` on your machine.
If a teammate needs the same session — for example, during an on-call
incident — you can export it:

```bash
sentinel auth export myorg \ --host staging.example.com \ --out /secure-share/staging-session.json \ --i-acknowledge
```

The `--i-acknowledge` flag is mandatory; without it the command
refuses to run. SentinelQA also prints a stderr warning every time:

> WARNING: writing plaintext session export. Treat the output file
> like a password manager backup. Encrypt it before sharing.

Transport the file using your standard secrets-handling channel
(1Password, encrypted USB, age-encrypted Slack DM — never plaintext
email or chat). On the receiving machine:

1. Run `sentinel auth login myorg --url https://staging.example.com/` once so the keyring master key exists.
2. Drop the file at `<run-dir>/auth/storage_state.json` and point the TS runner at it via `sentinel-ts run --storage-state /path`, OR
3. Re-import it into the vault by re-capturing (the canonical path — sharing the encrypted vault file directly across machines is a future enhancement).

When the teammate is done, both of you should:

```bash
sentinel auth revoke myorg --host staging.example.com
shred /secure-share/staging-session.json
```

`auth revoke` is idempotent; running it twice is safe.

---

## Reference

- `sentinel auth login` — capture a session interactively.
- `sentinel auth list` — list vault entries (redacted metadata only).
- `sentinel auth list-profiles` — show the built-in OAuth + LLM-web profiles.
- `sentinel auth revoke <name> --host <host>` — delete one entry.
- `sentinel auth revoke --all` — delete every entry (requires typed confirmation; refused in CI without `--yes-i-mean-it`).
- `sentinel auth export <name> --host <host> --out <path> --i-acknowledge` — decrypt and write the plaintext storage_state.

For the vault's on-disk layout, cryptography choices, and
audit-log contract, see [`docs/dev/auth-internals.md`](../dev/auth-internals.md).
For how to add a custom profile, see
[`docs/dev/auth-profiles.md`](../dev/auth-profiles.md).
