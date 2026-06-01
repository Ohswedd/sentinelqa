<!--
SentinelQA pull request template. Tick every box before merging.
-->

## Summary

<!-- One short paragraph: what changes, and why. -->

## Linked

- Closes: <!-- #123 or "none" -->
- ADR(s) added or updated: <!-- docs/adr/00NN-…md, or "none" -->

## Definition of Done

- [ ] Implementation matches the documented behavior.
- [ ] Tests added or updated (unit + integration / CLI / schema / security
      policy / report — whichever apply).
- [ ] `make ci` is green locally on the branch tip.
- [ ] Public documentation updated when CLI / SDK / MCP / config / report
      shapes change.
- [ ] ADR added or updated when an architectural decision is made.
- [ ] No secrets, tokens, or real customer data introduced (gitleaks
      verified).
- [ ] No `Co-authored-by:` trailer naming any AI tool (the
      no-ai-coauthor workflow verifies this).
- [ ] Conventional Commits used; commitlint green.
- [ ] `git status` clean after the final commit.

## Safety review

- [ ] No stealth, CAPTCHA bypass, fingerprint evasion, rate-limit bypass,
      cookie / session theft, or destructive defaults introduced.
- [ ] Any new scanner or probe enforces the target allowlist.
- [ ] New findings include evidence and a safe remediation note.

## Reviewer note

A human reviewer must approve this PR. Direct merges to `main` are blocked
by branch protection.
