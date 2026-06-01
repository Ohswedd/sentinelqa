---
title: Contributing
description: How to propose changes to SentinelQA.
status: Stable
---

SentinelQA is built phase-by-phase against a fixed plan (see
the build plan). Contributions are welcome inside the active phase and as
issues / discussions for future phases.

## Authority order

When instructions conflict, this order wins :

1. System / developer safety rules
2. User instructions
3. our engineering rules
4. our product spec
5. ADRs
6. Inline code comments

If our engineering rules and the the documentation conflict, stop, resolve the conflict in
the docs, and commit the correction before doing anything else.

## Branches

```
feature/<name> fix/<name> docs/<name>
refactor/<name> security/<name> ci/<name>
```

Never work directly on `main`.

## Commits

Conventional Commits, no `Co-authored-by:` trailers for AI tools
:

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

Before any commit :

1. Format (`make format`)
2. Lint (`make lint`)
3. Typecheck (`make typecheck`)
4. Unit tests + relevant integration / CLI / schema / security tests
5. the documentation / our engineering rules updated if behavior changed
6. ADR added for any our engineering rules §34 trigger

`make ci` runs all of the above. The bar is **all gates green** —
weakening tests to force green is forbidden.

## No fake completion

Per our engineering rules §37, the following are forbidden in delivered work:

- Hardcoded scores
- Empty returns dressed as success
- Untracked `TODO` comments
- Placeholder modules pretending to work
- Weakened tests to force green
- `xfail` / `skip` without an expiry
- Env-var-gated capabilities required by the phase's the documentation section

If you cannot finish something in scope, **re-home** it with a real
task file in a future release folder, or remove it from scope with an
Accepted ADR. Hand-waving is not closure.
