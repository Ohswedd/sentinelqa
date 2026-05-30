# Task 31.02 — `sentinel auth login` interactive flow

## Deliverables

- `apps/cli/src/sentinel_cli/commands/auth_cmd.py` — Typer subapp
  `sentinel auth` with the `login` command.
- `sentinel auth login <name> --url <login-url> [--target <host>]
  [--ttl <hours>] [--browser chromium|firefox|webkit]`:
  1. Resolve `<host>` from `<login-url>` if not explicit; reject if
     the host is not in the target allowlist (CLAUDE.md §6 — re-uses
     `engine.safety.policy.SafetyPolicy.enforce`).
  2. Launch a **headed** Playwright browser at `<login-url>` with
     `storage_state` empty.
  3. Print a clear human banner to stderr:
     > SentinelQA opened a real browser at <url>. Sign in with your
     > own credentials. When you're done, press Enter here. SentinelQA
     > will then capture the session and encrypt it locally. Your
     > credentials are NEVER transmitted to SentinelQA.
  4. Wait for the user to press Enter (or the Playwright `page.url`
     to leave the login origin AND the page to settle).
  5. Capture `context.storage_state()`, hand to
     `Vault.put(host, name, state, expires_at=now + ttl)`.
  6. Audit-log entry: `auth.login {host, name, browser,
     captured_cookies_count, captured_localstorage_count, ttl_hours}`.
     **Never** log cookie values or local-storage payloads.
- The command is `--ci`-rejected: there is no way to drive an
  interactive sign-in in CI. Exit 2 with a clear error message in
  `--ci` mode.
- The command refuses to overwrite an existing entry unless
  `--force` is passed.

## Tests required

- `tests/integration/auth/test_login_flow.py` (gated by
  `SENTINELQA_HAS_CHROMIUM=1`) — drives a stub login HTML page +
  asserts vault entry is written.
- `tests/unit/auth/test_login_cmd.py` — `--ci` rejection; unauthorized
  host rejection; `--force` semantics; audit-log content shape (no
  cookie values).

## Definition of Done

- [ ] Interactive flow works on darwin + linux.
- [ ] `--ci` always exits 2 (never tries to launch).
- [ ] Audit-log entry never contains a cookie / token value.
- [ ] `STATUS.md` updated.
