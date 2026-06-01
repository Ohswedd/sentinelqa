# Auth profiles

> Status: **Stable** (Phase 31, ADR-0043).

An **auth profile** is a small frozen dataclass that documents one
sign-in flow. It is metadata only — it has no fields for usernames,
passwords, tokens, or any other credential material, and an AST guard
(`tests/security/test_no_credentials_in_profiles.py`) refuses any
contribution that adds one.

The profile is used by `sentinel auth login` to (1) print the right
banner before opening a real browser, (2) auto-detect that sign-in
finished without the operator having to press Enter, and (3) cite the
provider's Terms of Service so the operator knows what they are
agreeing to.

---

## Built-in profiles

| Name              | Category  | Login host                |
| ----------------- | --------- | ------------------------- |
| `google-oauth`    | `oauth`   | accounts.google.com       |
| `github-oauth`    | `oauth`   | github.com                |
| `microsoft-entra` | `oauth`   | login.microsoftonline.com |
| `claude-ai`       | `llm-web` | claude.ai                 |
| `chatgpt-web`     | `llm-web` | chatgpt.com               |
| `chatgpt-codex`   | `llm-web` | chatgpt.com               |
| `google-gemini`   | `llm-web` | gemini.google.com         |
| `mistral-le-chat` | `llm-web` | chat.mistral.ai           |

`sentinel auth list-profiles --json` prints the full structured
metadata for every profile, including the success-URL patterns the
login flow watches and the ToS URL it cites.

---

## Adding a custom profile

1. Open `engine/auth/profiles/builtin.py`.
2. Append a new `AuthProfile` literal: `python _MY_PROFILE = AuthProfile( name="my-profile", label="My App", login_url_pattern="https://example.com/login", success_url_patterns=( "https://example.com/dashboard", ), mfa_hint="Approve in your authenticator app.", tos_url="https://example.com/terms", category="oauth", # or "llm-web" ) `

3. Add the constant to the `BUILTIN_PROFILES` tuple in the same file.
4. The `AuthProfile.__post_init__` validator enforces: - Every URL is HTTPS with a host. - `success_url_patterns` is non-empty. - `category` is `"oauth"` or `"llm-web"`.
5. Field names like `password`, `secret`, `token`, `key`, `credential`, `otp` will fail the AST guard. If you have a legitimate non-credential field whose name happens to contain one of those substrings, add it to the `_ALLOWED_FIELDS` set in `tests/security/test_no_credentials_in_profiles.py` with a comment explaining why.

6. Add a parametrized entry to `tests/unit/auth/test_profiles.py::test_profile_urls_are_https_and_have_hosts` so the URL-shape guard runs against your profile.

That's it — there is no registry plumbing to wire up. Profiles are
just data; selection happens at the CLI via `--profile <name>`.

---

## Why not let profiles handle credentials?

Because we never want to be in the credential-handling business.
our engineering rules; our engineering rules
Adding even an optional `username_env` field on the profile dataclass
would mean SentinelQA touches credentials, and the security boundary
between "what SentinelQA knows" and "what your browser knows" would
collapse. The interactive login flow — operator signs in in their own
browser, SentinelQA captures the session cookies via
`context.storage_state()` — keeps that boundary intact.
