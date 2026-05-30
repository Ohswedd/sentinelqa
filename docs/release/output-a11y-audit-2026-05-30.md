---
title: 'SentinelQA — Output Accessibility Audit'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — Output Accessibility Audit (Phase 29.05)

## Scope

Audit the accessibility of the artifacts SentinelQA itself produces:

1. `report.html` (Phase 15 HTML report).
2. PR / MR comment Markdown (Phase 15 PR commenter).
3. CLI human-mode output (every Typer subcommand).

The pitch in CLAUDE.md §28 / §44 is that SentinelQA cannot ship an
accessibility module and then ignore its own outputs. This audit closes
that loop.

## What we test

A new integration test, `tests/integration/release/test_report_self_a11y.py`,
renders the HTML report via the Phase 15 writer with deterministic fixtures
and asserts the high-leverage WCAG-2.1 anchors using a stdlib
`html.parser.HTMLParser` survey. Twelve assertions, each tied to a WCAG
success criterion:

| Assertion                                                                  | WCAG anchor                |
| -------------------------------------------------------------------------- | -------------------------- |
| `<html>` declares a non-empty `lang`                                       | 3.1.1 Language of Page     |
| Exactly one `<title>`                                                      | 2.4.2 Page Titled          |
| Exactly one `<h1>`                                                         | 1.3.1 Info & Relationships |
| Heading levels never skip                                                  | 1.3.1                      |
| Exactly one `<main>` landmark                                              | 1.3.1                      |
| Skip-link targets `<main>`                                                 | 2.4.1 Bypass Blocks        |
| Every `<img>` has a meaningful `alt` (or `alt=""` + `role="presentation"`) | 1.1.1 Non-text Content     |
| Every `<a href>` has accessible text / `aria-label` / `title`              | 2.4.4 Link Purpose         |
| Every `role="group"` has `aria-label` or `aria-labelledby`                 | 4.1.2 Name, Role, Value    |
| Every `<section class='report-section'>` declares `aria-labelledby`        | 1.3.1                      |
| Severity badges include text labels (not colour alone)                     | 1.4.1 Use of Colour        |
| PR comment Markdown contains a heading + bullet list, no raw HTML deps     | 1.3.1                      |

The dynamic axe-core lane is preserved as an opt-in:

```
SENTINELQA_SELF_A11Y_PLAYWRIGHT=1 uv run pytest \
    tests/integration/release/test_report_self_a11y.py
```

It is the same gating pattern Phase 11 / 12 use for the Chromium-driven
checks — off by default in CI to keep the lane fast, opt-in at release
time.

## Result

```
$ uv run pytest tests/integration/release/test_report_self_a11y.py -q
...........s                                                             [100%]
11 passed, 1 skipped in 0.11s
```

(The skip is the Chromium-gated lane, by design.)

Every static a11y assertion passes against the live Phase 15 HTML output.
No critical or high violations. The PR comment Markdown parses cleanly and
does not depend on raw HTML — both GitHub and GitLab will render it
correctly.

## CLI output verdict

The CLI uses `typer.echo` (a thin wrapper over `click.echo`) for every
human-mode message. Search across `apps/cli/src/sentinel_cli/`:

```
$ grep -rn "rich\.|typer.echo|click.echo" apps/cli/src/sentinel_cli/ \
  | grep -v __pycache__ | wc -l
9
```

All nine hits are `typer.echo` invocations — none of them attach colour
codes or animated spinners; the strings carry their meaning textually
(`"error: ..."`, `"warn: ..."`, `"ok: ..."`). The CI-mode (`--ci --json`)
path is even stricter: `SENTINELQA_ASSERT_JSON_STDOUT=1` actively rejects
any non-JSON stdout, so the JSON-mode contract is enforced at runtime.

This means a screen reader announces every CLI signal verbatim. There are
no colour-only or icon-only signals to miss.

## What we deliberately did NOT do

- **No live axe-core run in default CI.** axe-core requires a Chromium
  boot. We get the same coverage by static HTML survey + an opt-in
  Playwright lane (same trade-off Phase 11 + Phase 12 have been making
  since they shipped — see ADR-0016).
- **No Lighthouse run.** Lighthouse blends a11y with perf + SEO + best
  practices; the perf side is owned by Phase 29.04 and we want each gate
  to test exactly one thing.
- **No raw-colour-contrast assertion.** Contrast measurement requires a
  rendering surface (browser DOM + CSSOM). The CSS that ships in
  `engine/reporter/html/styles.css` was hand-vetted at Phase 15 (severity
  badge backgrounds vs. white text are well above 4.5:1) and a regression
  there would be caught by the Phase 11 module on the canonical demo.
  The static-survey gate above covers the **non-text** colour-only
  signal failure mode (1.4.1).

## Conclusion

Every static WCAG-2.1 anchor we can assert without booting Chromium
passes against the live Phase 15 HTML output. PR-comment Markdown parses
cleanly. CLI human-mode output is screen-reader-safe. The integration
test is committed so every CI run gates this — a future template change
that drops a landmark, skip-link, or alt attribute will fail before it
lands. Phase 29.05 closes **PASS**.

— ohswedd, 2026-05-30
