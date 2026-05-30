# Task 35.08 — Flip the repo public (owner-gated)

## Deliverables

- `docs/release/go-public-checklist.md` — pre-flight checklist the
  owner runs before flipping visibility. Required items:
  - All seven prior Phase 35 tasks `done`.
  - `make ci` green on `main`.
  - `make test-full` green on `main`.
  - Pre-1.0 review (`docs/release/pre-1.0-review.md`) signed for
    v0.7.0 (trademark rows complete).
  - `gitleaks detect --no-git --redact` over the full repo is clean.
  - No `.env` / `.env.local` / `~/.aws/` / `~/.config/` files in the
    tree.
  - All ADRs in `docs/adr/` are `Accepted` or `Superseded` (no
    `Draft` left).
  - The "Public release" announcement draft in
    `docs/release/announcement-draft.md` reviewed.
- The actual flip is **owner-gated**:
  ```bash
  gh repo edit Ohswedd/sentinelqa --visibility public
  gh repo edit Ohswedd/sentinelqa --description "Playwright-native release-confidence engine for LLM-built apps"
  gh repo edit Ohswedd/sentinelqa --homepage "https://docs.sentinelqa.dev"
  gh repo edit Ohswedd/sentinelqa --add-topic playwright,llm,testing,qa,ai,security,release-confidence
  ```
  These commands are documented; the agent does NOT run them.
- After the flip, owner:
  1. Uploads the social-preview PNG via the GitHub UI.
  2. Enables GitHub Private Vulnerability Reporting.
  3. Applies the branch-protection rules from task 35.06.
  4. Verifies the docs site is reachable.

## Tests required

- `tests/integration/release/test_go_public_checklist.py` — every
  checklist item references a file that exists; the checklist itself
  is a valid Markdown list.

## Definition of Done

- [ ] Checklist + announcement draft + commands ship.
- [ ] Repo is **not yet public** (this is the owner's call to make).
- [ ] `STATUS.md` updated.
