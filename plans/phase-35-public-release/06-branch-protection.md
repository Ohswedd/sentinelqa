# Task 35.06 — Branch protection + CODEOWNERS

## Deliverables

- `CODEOWNERS` already exists; verify every top-level directory has
  at least one human owner. Pre-1.0: `@ohswedd` is the global owner.
- `docs/dev/branch-protection.md` documents the rules that the owner
  enables on the public repo via GitHub UI / `gh api`:
  - `main` requires:
    - PR with at least one human reviewer (≠ author).
    - All `ci.yml` required checks green:
      `python (3.11)`, `python (3.12)`, `typescript (node 20)`,
      `typescript (node 22)`, `docs (Astro Starlight)`,
      `commitlint`, `gitleaks`, `lychee`, `no-ai-coauthor`.
    - Conversation resolution required.
    - "Require signed commits" recommended (owner toggles).
    - No force pushes; no deletions.
  - Tags `v*` are protected — push restricted to admin.
- `make verify-branch-protection` calls `gh api
  repos/Ohswedd/sentinelqa/branches/main/protection` and prints a
  diff against the documented rule-set. Diff non-empty → exit 1.
  (After the repo is public.)

## Tests required

- `tests/integration/release/test_branch_protection_doc.py` —
  documented rule list parses; sanity-checks reference real workflow
  names.

## Definition of Done

- [ ] `docs/dev/branch-protection.md` is the source of truth.
- [ ] `make verify-branch-protection` ships (owner runs it after the
      flip).
- [ ] `STATUS.md` updated.
