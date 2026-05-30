# Task 31.06 — Wire vault sessions into the runner / discovery / modules

## Deliverables

- New `auth.strategy: "browser_session"` config branch (in addition to
  the existing `test_user` and `none`):
  ```yaml
  auth:
    strategy: browser_session
    session_name: github-myorg
    # host inferred from target.base_url
  ```
- `engine/config/schema.py` extended to validate the new branch and
  reject inconsistent combinations (e.g. `browser_session` without a
  resolvable `session_name`).
- TS runner (`packages/ts-runtime/src/cli.ts`) accepts a `--storage-state
  <path>` flag and forwards to Playwright's `context.storageState`.
- Python orchestrator: when `auth.strategy == "browser_session"`, the
  lifecycle decrypts the vault entry into a `tmpfile` under
  `<run_dir>/auth/storage_state.json` (chmod `0600`, deleted on run
  teardown), passes the path to `sentinel-ts run --storage-state ...`.
- Discovery's `Crawler` learns to honour the same vault entry when
  running pre-test discovery against an authenticated app (cookies
  injected into the `httpx.Client`).
- Modules that already speak through the runner (functional,
  accessibility, performance, visual, chaos, llm_audit) inherit the
  authenticated session automatically — no module change needed.
- Audit-log entry on session use: `auth.session_used {host, name,
  cookies_count, age_seconds}`.

## Tests required

- `tests/integration/auth/test_runner_session_wiring.py` — end-to-end:
  vault → decrypt → write tmpfile → runner reads it → cookies arrive
  at a stub HTTP server.
- `tests/integration/auth/test_crawler_session_wiring.py` — same for
  the Python crawler.
- `tests/security/test_session_tmpfile_lifetime.py` — tmpfile is
  created with `0600`, deleted on teardown, NOT included in
  `latest`-symlink, NOT copied into report artifacts.

## Definition of Done

- [ ] Authenticated audit works end-to-end on the Phase 26 Next.js
      example (`auth.strategy: browser_session` + a vault entry).
- [ ] Session tmpfile never leaks to a persisted artifact.
- [ ] `STATUS.md` updated.
