---
title: Generator module
description: Deterministic Playwright spec generator with semantic locators.
status: Stable
---

The generator turns a `TestPlan` into Playwright `*.spec.ts` files under
`tests/sentinel/`. Templates are Jinja2 with `StrictUndefined` and a
mandatory banner so re-runs preserve hand-edited content.

.

## Outputs

- `tests/sentinel/<flow>/*.spec.ts` — generated specs (banner-protected)
- `tests/sentinel/page-objects/*Page.ts` — one POM per high-traffic route
- `tests/sentinel/fixtures/*.ts` — auth / data / global setup-teardown
- `tests/sentinel/_plan.md` — human-readable diff vs prior run

## Semantic locators

Generated specs prefer Playwright's semantic locators in this order:

1. `page.getByRole(...)`
2. `page.getByLabel(...)`
3. `page.getByPlaceholder(...)`
4. `page.getByText(...)`
5. `page.getByTitle(...)`

Brittle selectors (`:nth-of-type`, raw XPath, nested-div soup) are
flagged by `sentinel-ts audit-locators` and refused at generate time
unless `--allow-brittle` is set.

## Hand-edit safety

Each generated file starts with a banner:

```ts
// SENTINELQA AUTO-GENERATED — do not edit by hand
// generated_at: 2026-05-28T12:00:00Z
```

If the banner is missing or the file's `mtime` has drifted, the
generator refuses to overwrite (exit 6) unless `--force`.

## CLI

```bash
uv run sentinel generate --url http://127.0.0.1:5001 --from-plan
```
