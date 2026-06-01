# ADR-0020: HTML, PR-comment, Slack, and trends reports

## Status

Accepted

<!-- Date: 2026-05-29 -->
<!-- Authors: @ohswedd -->

## Context

shipped the **machine-readable** report envelopes —
`run.json` / `findings.json` / `score.json` / `junit.xml` /
`sarif.json` / `report.md` — plus the dispatcher (`engine.reporter.Reporter`)
that ties them to the run lifecycle. The HTML report and the
GitHub PR-comment / Slack summary payloads were left as Phase-15
placeholders so the wire formats could stabilize first.

the documentation (Reporter module) and §38 (Report rules) require the
release-confidence report to answer, in one place:

```
What happened? Where? How severe? How confident?
What evidence exists? Why does it matter?
How should it be fixed? Does it block release?
```

our engineering rules(Report rules) tightens the contract:

- Reports must serve developers, QA, security reviewers, managers, and agents.
- Machine-readable reports must be schema-stable and versioned.

our engineering rules(Privacy and telemetry) plus the documentation require:

- No external network calls when viewing a report.
- No CDN-hosted assets, no fonts or scripts loaded from third parties.

the documentation (PR comment) and §38 (Trend if history exists) define the
PR-comment and trends content set.

ships the four artifacts that turn the persisted run state
into a human-readable answer:

1. A self-contained `report.html`.
2. A GitHub-flavored Markdown PR comment with an upsert anchor.
3. A trend overlay derived from prior local runs.
4. A Slack Block Kit payload (generated only — posting lands in).

Plus the `sentinel report` command that drives re-rendering on demand.

our engineering rules"report schema" as an ADR trigger — both the new
HTML wire format and the Slack payload schema fall under that rule.

## Decision

We add five new modules under `engine/reporter/` plus an asset folder
and one new CLI surface:

1. **`engine/reporter/html/`** — bundled Jinja2 template (`template.html.j2`), `styles.css`, `app.js`. Assets are inlined at render time so the produced `report.html` is a single self-contained file.

2. **`engine/reporter/html_writer.py`** — owns `render_html_report`, `write_html`, `HtmlReportInputs`, and `collect_artifact_links`. `HTML_REPORT_SCHEMA_VERSION = "1"` locks the template shape. The build-context step (`build_template_context`) is a pure function so tests can assert on the shape rather than parse rendered HTML.

3. **`engine/reporter/pr_comment.py`** — `render_pr_comment` returns GitHub-flavored Markdown. Every dynamic string flows through `engine.reporter.markdown_writer.md_escape` to prevent injection; the comment is anchored with the literal HTML comment `<!-- sentinelqa:pr-comment -->` so the Phase-17 GitHub Action can upsert it.

4. **`engine/reporter/trends.py`** — `compute_trends(runs_root)` walks the local `.sentinel/runs/<id>/` history (no telemetry, no cloud) and emits a `TrendData` with three series: total score, per-module pass rate, and top recurring finding IDs. Sparklines are inline SVG (no JS chart library).

5. **`engine/reporter/audit_view.py`** — `load_audit_entries(path)` reads the redacted audit JSONL and normalizes it for the HTML audit-trail section. Malformed lines are dropped silently — trends and the audit view never block the report.

6. **`engine/reporter/slack.py`** — `render_slack_payload` returns a Slack Block Kit JSON dict, plus `write_slack_payload` for on-disk persistence and `load_block_kit_schema` for validation. The vendored Block Kit subset schema lives at `packages/shared-schema/external/slack-block-kit.schema.json`. We do NOT post to Slack here — owns the integration.

7. **`engine/reporter/dispatcher.py`** — wires the HTML writer behind the existing `Reporter.emit` flow. `SUPPORTED_FORMATS` gains `"html"`; the `_FORMAT_ALIASES` map drops the `html → ` placeholder. The dispatcher reads the audit log and computes the trend overlay before rendering so the HTML embeds them.

8. **`sentinel report`** — the Phase-14 explainer is kept (`sentinel
report --explain-score`). The new re-render path (`sentinel report --latest`, `sentinel report --run-id RUN-...`) reads the persisted artifacts and re-renders the requested formats (`--format html,json,sarif,junit,md`). The re-render is idempotent: it never writes audit-log entries (the audit log is a one-shot record of the original run's decisions per the engineering guidelines). `--open` opens the HTML in the default browser, skipped in CI.

Reports stay offline by design:

- No `<link rel="stylesheet">` / `<script src=>` / `<img src=>` / `<iframe src=>` may reference an external host.
- `tests/integration/reporter/test_html_self_contained.py` is the drift guard.

The HTML must also pass our own structural accessibility checks:

- `<main>` landmark + skip link, `<html lang="en">`, hierarchical headings, alt text on every image, accessible names on every form control.
- `tests/integration/reporter/test_html_self_a11y.py` runs these checks on every CI run.

## Consequences

- Reports are now first-class: every run that writes `run.json` also writes `report.html` when `html` is in `config.report.formats`.
- The HTML schema (`HTML_REPORT_SCHEMA_VERSION`) joins the locked set; any breaking template change bumps the version.
- The PR-comment anchor + upsert flow means the GitHub Action can edit the same comment on every push without spawning new ones.
- The Slack payload validates against the vendored Block Kit schema; can post it directly.
- Trend rendering is local-only — cloud remains an explicit opt-in.
- `sentinel report` makes re-rendering cheap: a reviewer who lost the HTML can recover it from `run.json` + `findings.json` + `score.json` without re-executing modules.
- Coverage gate ≥ 85 % for `engine.reporter` is met at 96 %.

## Alternatives considered

- **Bundle a JS chart library** (Chart.js, ApexCharts, etc.) for trend sparklines. Rejected — would either pull a CDN or balloon the bundle size, and a sparkline is well served by inline SVG.
- **Markdown-only PR comment, no HTML**. Rejected — the HTML is the canonical artifact for everyone past the PR author (security reviewers, managers). The Markdown serves the PR-comment workflow specifically.
- **Post to Slack from `engine/reporter/slack.py`**. Rejected — the Slack integration is a Phase-25 deliverable. Generating the payload here lets us lock its shape today without wiring a Slack token into the engine.
- **Re-execute modules during `sentinel report`**. Rejected — the re-render path is for "I lost the artifacts, give me the report back" and must be idempotent. Re-execution lives in `sentinel
audit`.
- **Auto-accept HTML evidence images at render time**. Rejected for — the evidence drawer lazy-loads images via relative paths but never inlines them; that preserves the audit chain and avoids bloating the HTML for large traces. Inline evidence rendering could land later if needed.

## References

- the documentation Reporter module
- the documentation PR comment
- our product spec (within the §38 "What a useful report answers" framing)
- our engineering rules
- our engineering rules(ADR triggers)
- our engineering rules
- our engineering rules
- Slack Block Kit reference — https://api.slack.com/block-kit
