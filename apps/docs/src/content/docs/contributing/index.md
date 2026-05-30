---
title: Contributing
description: How to propose changes to SentinelQA.
status: Stable
---

SentinelQA is built phase-by-phase against a fixed plan (see
`plans/`). Contributions are welcome inside the active phase and as
issues / discussions for future phases.

## Authority order

When instructions conflict, this order wins (CLAUDE.md §2):

1. System / developer safety rules
2. User instructions
3. `CLAUDE.md`
4. `PRD.md`
5. ADRs
6. Inline code comments

If `CLAUDE.md` and the PRD conflict, stop, resolve the conflict in
the docs, and commit the correction before doing anything else.

## Branches

```
feature/<name>      fix/<name>          docs/<name>
refactor/<name>     security/<name>     ci/<name>
```

Never work directly on `main`.

## Commits

Conventional Commits, no `Co-authored-by:` trailers for AI tools
(CLAUDE.md §3):

```
feat(scope): summary
fix(scope): summary
docs(scope): summary
test(scope): summary
refactor(scope): summary
security(scope): summary
ci(scope): summary
chore(scope): summary
```

## Quality gates

Before any commit (CLAUDE.md §17):

1. Format (`make format`)
2. Lint (`make lint`)
3. Typecheck (`make typecheck`)
4. Unit tests + relevant integration / CLI / schema / security tests
5. PRD / CLAUDE.md updated if behavior changed
6. ADR added for any CLAUDE.md §34 trigger

`make ci` runs all of the above. The bar is **all gates green** —
weakening tests to force green is forbidden.

## No fake completion

Per CLAUDE.md §37, the following are forbidden in delivered work:

- Hardcoded scores
- Empty returns dressed as success
- Untracked `TODO` comments
- Placeholder modules pretending to work
- Weakened tests to force green
- `xfail` / `skip` without an expiry
- Env-var-gated capabilities required by the phase's PRD section

If you cannot finish something in scope, **re-home** it with a real
task file in a later phase folder, or remove it from scope with an
Accepted ADR. Hand-waving is not closure.
