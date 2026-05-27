# Task 00.04 — Secret hygiene

## Objective

Make it structurally impossible to commit secrets, credentials, or AI-vendor keys. SentinelQA itself handles tokens, cookies, and private keys (PRD §23.1) — leaking even one would compromise the product's trust thesis.

## Prerequisites

- Tasks 00.01–00.03 complete.

## Deliverables

- A repo-wide `.gitignore` covering:
  - Python: `__pycache__/`, `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`, `htmlcov/`.
  - Node: `node_modules/`, `.turbo/`, `.next/`, `.svelte-kit/`, `dist/`, `.pnpm-store/`.
  - Playwright: `playwright-report/`, `test-results/`, `traces/`.
  - SentinelQA runtime: `.sentinel/runs/`, `.sentinel/baselines/`, `.sentinel/reports/`, `.sentinel/cache/`.
  - Editors / OS: `.DS_Store`, `.idea/`, `.vscode/` (allow `.vscode/extensions.json` only), `*.swp`.
  - Secrets: `.env`, `.env.*`, `!*.env.example`, `secrets.*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `*.pfx`.
- `.env.example` listing every environment variable the PRD references or any future module will need, each with a one-line comment and a safe placeholder. Required entries today:
  - `TEST_USER_EMAIL=test+user@example.com`
  - `TEST_USER_PASSWORD=replace-me-locally`
  - `SENTINEL_LOG_LEVEL=info`
  - `SENTINEL_CI=false`
  - `OPENAI_API_KEY=` (placeholder; only used if/when the planner LLM adapter is enabled)
  - `ANTHROPIC_API_KEY=` (same)
  - `BROWSERSTACK_USERNAME=` / `BROWSERSTACK_ACCESS_KEY=` (used only by Phase 25)
  - `SAUCE_USERNAME=` / `SAUCE_ACCESS_KEY=` (same)
  - `SLACK_WEBHOOK_URL=` (Phase 25)
- A redaction helper stub in `engine/policy/redaction.py` (real impl lands in Phase 01) — the *signatures* must be there so other phases can import.
- Pre-commit secret scan: `pre-commit` config with `detect-secrets` (or `gitleaks` mirror); baseline committed.
- A short `docs/dev/secret-hygiene.md` explaining the rules from `CLAUDE.md` §33.

## Steps

1. Write `.gitignore` from the list above. Verify with `git check-ignore .env` (should output `.env`).
2. Write `.env.example` and commit it. Verify `.env` itself is **not** in the repo (`git ls-files | grep '\.env$'` returns nothing).
3. Add `.pre-commit-config.yaml` with `detect-secrets` (or a vetted equivalent). Generate `.secrets.baseline` and commit it.
4. Install the hook locally and add `pre-commit install` to `make install`.
5. Create the redaction stub file with a single function signature `def redact(value: str | dict | list) -> str | dict | list: ...` raising `NotImplementedError` — this is the only allowed `NotImplementedError` until Phase 01 fills it in (`CLAUDE.md` §37).
6. Write `docs/dev/secret-hygiene.md`.

## Acceptance criteria

- A deliberate test commit containing `OPENAI_API_KEY=sk-fake-12345` is **rejected** by the pre-commit hook.
- A deliberate test commit containing an SSH private key block is rejected.
- `.env.example` is present; `.env` is not tracked.
- Redaction stub importable from `engine.policy.redaction`.

## Tests required

- Manually verify the pre-commit hook by attempting a poisoned commit on a throwaway branch, then aborting the commit. Document the verification in the PR description; do not commit the poisoned file.

## PRD / CLAUDE.md references

- PRD §23 Security/Threat Model, §33 (Reference Sources for OWASP).
- CLAUDE.md §3 Privacy & ownership, §33 Logging & secrets.

## Definition of Done

- [ ] `.gitignore` covers every category above.
- [ ] `.env.example` complete; `.env` not tracked.
- [ ] Pre-commit hook blocks fake secret.
- [ ] Redaction stub in place.
- [ ] `docs/dev/secret-hygiene.md` exists.
- [ ] `STATUS.md` updated.
