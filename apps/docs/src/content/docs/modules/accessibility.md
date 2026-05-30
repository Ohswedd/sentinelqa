---
title: Accessibility module
description: axe-core + deterministic keyboard / landmark / sr-name checks.
status: Stable
---

`sentinel a11y` performs per-route accessibility checks: axe-core for
WCAG rules, plus deterministic Python-side checks for keyboard reach,
landmark structure, and accessible-name presence.

Authority: PRD §10.4, ADR-0016, CLAUDE.md §28.

## Wording contract

Every product output begins with **"Automated accessibility check"** —
never "WCAG compliant," "fully accessible," or similar overreach
(CLAUDE.md §28). The guard test `tests/security/test_no_wcag_compliance_claims.py`
greps the entire module source on every CI pass.

## What it checks

| Check               | Source                                      |
| ------------------- | ------------------------------------------- |
| axe-core violations | injected per-route, deterministic ruleset   |
| Keyboard reach      | every interactive element reachable by Tab  |
| Landmark structure  | exactly one `main`, valid heading hierarchy |
| Accessible names    | every form control + interactive widget     |

## Severity mapping

| axe impact         | SentinelQA severity |
| ------------------ | ------------------- |
| critical / serious | high                |
| moderate           | medium              |
| minor              | low                 |

Confidence is 0.95 for stable axe rules, 0.6 for experimental, 0.9
for deterministic checks.

## CLI

```bash
uv run sentinel a11y --url http://127.0.0.1:5001 --routes "/,/login,/dashboard"
```

Routes can come from `--routes`, `discovery.json`,
`config.accessibility.routes`, or default to `("/")` for CLI-only
calls.
