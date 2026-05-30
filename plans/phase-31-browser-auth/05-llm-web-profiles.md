# Task 31.05 — LLM-web app auth profiles (Claude / ChatGPT / Codex / Gemini / Le Chat)

## Deliverables

- Five `AuthProfile` entries under `engine/auth/profiles/`:
  - `claude-ai` (claude.ai)
  - `chatgpt-web` (chat.openai.com / chatgpt.com)
  - `chatgpt-codex` (chat.openai.com/?model=code, plus the standalone
    `codex.openai.com` route if available)
  - `google-gemini` (gemini.google.com)
  - `mistral-le-chat` (chat.mistral.ai)
- Each profile carries:
  - `login_url_pattern`.
  - `success_url_patterns` — the entry pages each app routes to after
    sign-in, used to auto-detect completion.
  - `mfa_hint`.
  - `tos_url` — link to the provider's ToS.
- `docs/dev/llm-web-auth-profiles.md` documents:
  - Each profile, what it captures, what it does NOT capture.
  - Per-provider ToS notes — auditing **your own logged-in workflows
    on your own account** is acceptable; auditing other accounts, or
    scraping the web UI for content generation, is NOT what this is
    for. SentinelQA enforces this implicitly: the operator signs in
    themselves; SentinelQA never harvests credentials and never
    generates content via the web UI.
- **Documented use cases** (in `docs/user/auth-flows.md`):
  - Audit your own ChatGPT plugin / GPT's behaviour (does it leak
    PII? does it refuse the right things?).
  - Audit your own Claude Project workflow (e.g. an internal Claude
    Project URL).
  - Audit a Gemini extension you built that runs against your account.
- Same lint guard as task 31.04 — no credential-named fields.

## Tests required

- `tests/unit/auth/test_llm_web_profiles.py` — all five load; URL
  patterns resolve to the expected domains; ToS URLs are HTTPS.

## Definition of Done

- [ ] Five profiles ship.
- [ ] ToS docs cross-link to each provider's official terms.
- [ ] `docs/user/auth-flows.md` covers the headline use cases without
      claiming SentinelQA can drive LLM web UIs (it can't; it audits
      authenticated workflows of apps you own).
- [ ] `STATUS.md` updated.
