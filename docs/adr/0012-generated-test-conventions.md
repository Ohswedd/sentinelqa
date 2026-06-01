# ADR-0012: Generated test conventions

## Status

Accepted

<!-- Date: 2026-05-28 -->
<!-- Authors: @ohswedd -->

## Context

ships the Generator module : a `TestPlan` + `DiscoveryGraph` becomes idiomatic Playwright spec files, page objects, fixtures, and a human-readable generated plan markdown under `tests/sentinel/`. Several questions had to land in code:

1. **Templating engine.** our engineering rules"undefined variable" mode so missing template inputs fail loudly rather than silently producing broken TypeScript. Hand-rolling those primitives is precisely the case where a "boring, stable tool" is justified.
2. **Hand-edit safety.** Generated files MUST be re-generatable, but the project must NOT clobber files a human has edited. the documentation lists the generated tree under `tests/sentinel/` and `tests/sentinel/pages/`; users WILL hand-edit some files there.
3. **Brittleness audit placement.** our engineering rules/§22 require semantic locators. The audit logic already lives in TypeScript (`packages/ts-runtime/src/locators.ts`,); the question was whether to duplicate it in Python or invoke the TS side.
4. **Output determinism.** `sentinel generate` must be idempotent for the same plan, but the planner's auto-generated `FLW-*` / `TC-*` IDs change per run. Embedding those IDs in filenames or spec contents would break re-run reproducibility.
5. **Idiomatic vs. minimal.** Generated specs should look like code a Playwright developer would write. That means `sentinelTest` from `@sentinelqa/ts-runtime/playwright`, semantic locators, explicit assertions, and tags (`@p0`, `@auth`) per the planner.

## Decision

We adopt the following conventions for the Generator module:

1. **Templating: Jinja2 with `StrictUndefined`.** Templates live under `engine/generator/templates/*.j2`. `engine.generator.render.render_template(name, ctx)` enforces: - Strict undefined — a missing context key raises `RenderError`. - Mandatory banner — every rendered output must include `SentinelQA Generated — do not edit by hand` (the marker the writer searches for). - Two regex filters: `regex_literal` (escapes JS regex metacharacters; use for label literals) and `regex_pattern` (passes regex source verbatim; use when the caller intends alternation like `sign in|log in`). - One TS-string filter (`js_string`) that wraps values in `JSON.dumps`-quoted form.
2. **Hand-edit safety: banner-aware writer.** `engine.generator.writer.write_generated_files` is the only path that writes generated files. A file is considered SentinelQA-managed iff its first 4 KiB contain `SentinelQA Generated — do not edit by hand`. Hand-owned files (those without the marker) raise `OverwriteError` and the CLI exits 6 (`EXIT_TEST_EXECUTION_FAILED`) unless `sentinel generate --force` is passed. Writes are atomic (write to temp + `os.replace`).
3. **Brittleness audit: TS-owned, Python-orchestrated.** Audit logic stays in `auditLocatorBrittleness` (TS). Python invokes it through a new `sentinel-ts audit-locators --file <path>` subcommand and parses the JSON report (`{schema_version, files_scanned, findings[]}`). `engine.generator.locator_strategy.audit_specs` is the Python wrapper. The generator runs the audit on every spec BEFORE writing; any finding aborts the write and exits 6. The audit can be skipped via `--no-audit` (documented as local-debugging only, not for CI).
4. **Determinism: discovery IDs only, never planner IDs.** Spec filenames are derived from `extractor + flow.name` slug, never `flow.id`. When two flows would collide on filename (e.g. multiple form-submit flows whose route paths slugify identically), we append a stable disambiguator extracted from the flow's `form:FRM-*` / `endpoint:API-*` tags (discovery IDs are loaded from JSON and are byte-stable across runs). The remaining auto-generated ID tags (`flow:FLW-*`, etc.) are stripped from the rendered spec via `_stable_tags`. The full audit-trail tag list still lives in `plan.json`.
5. **Idiom: `sentinelTest` + semantic locators only.** Every generated spec imports `sentinelTest as test, expect` from `@sentinelqa/ts-runtime/playwright`. Locators use `getByRole` / `getByLabel` / `getByText` / `getByTestId`; raw `page.locator(...)` is used only for landmarks (`body`, `main`) and is allowlisted by the audit because it does not match brittle patterns. Tags (`@p0`, `@critical`, `@auth`, `@<flow.tags>`) are emitted in Playwright's `{ tag: [...] }` block so users can run `--grep @p0` without re-tagging.

## Consequences

- **Positive:** - `sentinel generate --from-discovery <run>` is bit-exact reproducible across machines and CI runs; CI can verify diffs the same way as code reviews. - The generator never silently breaks: missing template variables raise; missing banner raises; brittle locators block writes. - Hand-edits are preserved by default; users only opt into clobbering via explicit `--force`. - The brittleness audit lives once (TS) and is consumed by both the generator and the Healer. No duplicated rule set to drift. - Generated tests look like code a Playwright developer would write — matches our product spec example.
- **Negative / trade-off:** - Jinja2 adds one Python dependency (~250 KB). We accept it because hand-rolling `{{ var }}` + `{% for %}` + strict undefined would re-implement Jinja's core badly. - `sentinel-ts audit-locators` requires the TS dist to be built (`pnpm --filter @sentinelqa/ts-runtime build`). When the binary is missing, the audit fails closed (exit 6) — by design, but it means CI must build the TS package before invoking `sentinel generate`. - The banner-marker safety check is content-based; if a user deletes the banner from a generated file, SentinelQA will treat it as hand-owned and refuse to overwrite. This is the intended escape hatch. - Spec filenames embed `form:FRM-*` / `endpoint:API-*` disambiguators when needed; those make filenames longer than the bare extractor slug. We truncate at 120 chars to stay under typical OS limits.
- **Follow-up obligations:** - (Healer) consumes the same brittleness audit (`auditLocatorBrittleness`); the rule set must not regress when ships repair proposals. - (Docs) must document the banner convention so hand-edits are deliberate. - The data fixture's `authorized_destructive` gate is the only safe path to seed users at runtime; (CI integration) must surface this when the user generates against a non-local target.

## Alternatives considered

- **f-string / `string.Template` templating.** Rejected: the templates need loops, conditionals (`{% if anchor_role %}`), and `StrictUndefined`-equivalent failure modes. Building those on top of `str.format` reproduces Jinja2 with worse error messages.
- **Mustache / Handlebars.** Rejected: not Python-native, no strict-undefined mode, and the team would have to learn a syntax we don't use elsewhere.
- **Duplicate the audit rules in Python.** Rejected: the TS audit lives next to the locator strategies it understands; duplicating in Python would drift the moment extends the audit, and we'd have two sources of truth for what counts as "brittle."
- **Embed `flow.id` in spec filenames.** Rejected: would make every re-run produce different filenames, breaking `git diff` reviews and CI artifact caching.
- **Auto-merge hand-edits with generated content.** Rejected: ambitious, fragile, and silently dangerous. The banner-marker + explicit `--force` is conservative and matches Git's posture toward unmerged conflicts.

## References

- the documentation section(s): the documentation (Generator module), our product spec (Example Generated Playwright Test), our product spec (Generated Test Rules), our product spec (TypeScript Runtime)
- our engineering rules rule(s): our engineering rules(TS rules), our engineering rules(Generated test rules), our engineering rules(Self-healing rules), our engineering rules(Dependency rules), our engineering rules(No placeholder completion)
- Related ADRs: ADR-0009 (Python ↔ TS protocol), ADR-0010 (Discovery release HTTP-first), ADR-0011 (Planner deterministic vs LLM)
