<!--
SentinelQA PR template. Authority: our engineering rules (Definition of Done) and §5
(PRD discipline). Tick every box before merging.
-->

## What & why

<!-- One paragraph: what changes, and why. Reference the PRD section and/or
     plans/ task this implements. -->

## Linked

- Phase / task: <!-- e.g.  -->
- PRD section(s): <!-- e.g. the documentation -->
- ADR(s) added/updated: <!-- docs/adr/0007-…md, or "none" -->
- Closes: <!-- #123 or "none" -->

## Definition of Done (our engineering rules)

- [ ] Implementation matches PRD.
- [ ] Tests exist and pass (unit + relevant integration / CLI / schema /
      security policy / report — whichever apply per our engineering rules).
- [ ] `make ci` is green locally on the branch tip.
- [ ] our product spec updated if behavior, CLI/SDK contract, lifecycle, safety
      boundary, report schema, data model, or scoring changed
      (our engineering rules).
- [ ] ADR added/updated if a our engineering rules trigger was reached.
- [ ] No secrets, tokens, or real customer data introduced
      (our engineering rules; verified by gitleaks).
- [ ] No `Co-authored-by:` trailer naming any AI tool
      (our engineering rules; verified by the no-ai-coauthor workflow).
- [ ] Conventional Commits used; commitlint green.
- [ ] updated (active task marked done; pointer
      advanced).
- [ ] `git status` clean after the final commit.

## Safety review (our engineering rules, our product spec)

- [ ] No stealth, CAPTCHA bypass, fingerprint evasion, rate-limit bypass,
      cookie/session theft, or destructive defaults introduced.
- [ ] Any new scanner/probe enforces the target allowlist.
- [ ] New findings include evidence and a safe remediation note.

## Reviewer note

A human CODEOWNER must approve this PR. Direct merges to `main` are
blocked by branch protection.
