# Task 00.08 — LICENSE, CODEOWNERS, ownership lock

## Objective

Codify the project's open-core license intent (PRD §6.6) and lock down ownership so no AI vendor, tool, or model can be added as a Git owner, maintainer, or co-author (`CLAUDE.md` §3).

## Prerequisites

- Tasks 00.01–00.07 complete.

## Deliverables

- `LICENSE` at repo root. **Default choice: Apache-2.0** (developer-friendly, patent grant, matches open-core positioning). If the human owner prefers MIT or a dual license, capture that decision in a new ADR before this task is closed.
- `NOTICE` file if Apache-2.0 (lists third-party attributions to be appended as deps are added).
- `.github/CODEOWNERS` listing only the human owner(s). No bot accounts, no AI tools.
- `docs/dev/ownership.md` explaining:
  - The repo stays **private** until the human owner decides otherwise (`CLAUDE.md` §3).
  - Authorship rules: human owner or explicitly configured human identity only.
  - No `Co-authored-by: <ai-tool>` trailers — ever, unless the user explicitly types it themselves.
  - PR review requires at least one human owner approval.
- `docs/dev/trademarks-and-naming.md` placeholder noting that "SentinelQA" must be checked for trademark conflicts before any public release (Phase 28 owns this verification).

## Steps

1. Write the LICENSE.
2. Write the NOTICE file (empty third-party section if Apache-2.0).
3. Write CODEOWNERS with the human owner's GitHub handle.
4. Write `docs/dev/ownership.md` quoting `CLAUDE.md` §3 verbatim.
5. Add a CI guard: a workflow that fails if any commit message contains `Co-authored-by:` followed by a known AI-tool string (`Claude`, `GPT`, `Copilot`, `Gemini`, etc.). The guard lives at `.github/workflows/no-ai-coauthor.yml`.
6. Verify the guard by attempting a poisoned commit on a throwaway branch.

## Acceptance criteria

- LICENSE present and matches the ADR.
- CODEOWNERS lists only humans.
- `no-ai-coauthor` workflow blocks a poisoned commit.
- `docs/dev/ownership.md` quotes the relevant CLAUDE.md sections.

## Tests required

- Workflow-blocking demonstrated by a throwaway branch (poisoned commit deleted afterward).

## PRD / CLAUDE.md references

- PRD §6.6 Open-core principle, §28.1 differentiation positioning.
- CLAUDE.md §3 Privacy & ownership, §4 Git workflow.

## Definition of Done

- [ ] LICENSE + NOTICE committed.
- [ ] CODEOWNERS committed.
- [ ] Ownership doc + trademark placeholder committed.
- [ ] `no-ai-coauthor.yml` active and verified.
- [ ] `STATUS.md` updated.
