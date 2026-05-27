<!--
SentinelQA PR template. Authority: CLAUDE.md §18 (Definition of Done) and §5
(PRD discipline). Tick every box before merging.
-->

## What & why

<!-- One paragraph: what changes, and why. Reference the PRD section and/or
     plans/ task this implements. -->

## Linked

- Phase / task: <!-- e.g. plans/phase-05-discovery-module/01-crawler.md -->
- PRD section(s): <!-- e.g. PRD §9.1 -->
- ADR(s) added/updated: <!-- docs/adr/0007-…md, or "none" -->
- Closes: <!-- #123 or "none" -->

## Definition of Done (CLAUDE.md §18)

- [ ] Implementation matches PRD.
- [ ] Tests exist and pass (unit + relevant integration / CLI / schema /
      security policy / report — whichever apply per `CLAUDE.md` §16).
- [ ] `make ci` is green locally on the branch tip.
- [ ] `PRD.md` updated if behavior, CLI/SDK contract, lifecycle, safety
      boundary, report schema, data model, or scoring changed
      (`CLAUDE.md` §5).
- [ ] ADR added/updated if a `CLAUDE.md` §34 trigger was reached.
- [ ] No secrets, tokens, or real customer data introduced
      (`CLAUDE.md` §33; verified by gitleaks).
- [ ] No `Co-authored-by:` trailer naming any AI tool
      (`CLAUDE.md` §3; verified by the no-ai-coauthor workflow).
- [ ] Conventional Commits used; commitlint green.
- [ ] `plans/STATUS.md` updated (active task marked done; pointer
      advanced).
- [ ] `git status` clean after the final commit.

## Safety review (CLAUDE.md §6, PRD §2)

- [ ] No stealth, CAPTCHA bypass, fingerprint evasion, rate-limit bypass,
      cookie/session theft, or destructive defaults introduced.
- [ ] Any new scanner/probe enforces the target allowlist.
- [ ] New findings include evidence and a safe remediation note.

## Reviewer note

A human CODEOWNER must approve this PR. Direct merges to `main` are
blocked by branch protection.
