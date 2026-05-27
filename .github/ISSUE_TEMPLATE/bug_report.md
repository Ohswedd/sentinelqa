---
name: Bug report
about: Report incorrect behavior of SentinelQA itself (not findings produced by it).
title: 'bug: '
labels: ['bug', 'triage']
---

## What happened

<!-- One paragraph describing the actual behavior. -->

## What you expected

<!-- One paragraph describing the intended/documented behavior. -->

## Reproduction

```text
# exact commands, config, and CLI invocation
```

- SentinelQA version / commit:
- Python version: <!-- python3 --version -->
- Node version: <!-- node --version -->
- OS: <!-- uname -a -->

## Evidence

<!-- Attach logs / run.json / findings.json / screenshots from
     .sentinel/runs/<run-id>/. Redact secrets first
     (docs/dev/secret-hygiene.md). -->

## Affected PRD section(s)

<!-- e.g. PRD §9.4 Runner — helps the triage owner route the report. -->

## Safety boundary impact

- [ ] This bug affects the safety boundary (CLAUDE.md §6 / PRD §2). If
      checked, the report will be triaged under `security/`.
