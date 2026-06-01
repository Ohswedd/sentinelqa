# ADR-0046: Compliance Packs

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

The release shipped strong individual modules ( accessibility,
security, extended-security catalog,
supply-chain) but no first-class way to express _"run the subset of
checks relevant to WCAG 2.2 AA"_ or _"run the subset relevant to
GDPR"_. CI/CD operators were hand-wiring `--modules` flags plus
per-module options, which is brittle and easy to misconfigure.

Three asks shaped:

1. **Named compliance posture** — operators want one flag (`--compliance-pack <id>`) that pins the modules, options, and check filter for a given audit regime. Mis-spelled pack ids must fail at load time, not after a long run.
2. **WCAG 2.2 deterministic checks** — axe-core 4.10's `wcag22*` tag covers most of the new SCs, but several (focus-not-obscured, target-size-min, dragging-movements, redundant-entry, accessible-authentication) are page-shape dependent in ways axe's rule engine struggles with. ships deterministic Python functions for these and emits findings with `compliance_id:
wcag-2.2:<sc-id>`.
3. **the engineering guidelines** — the existing accessibility wording guard (no "fully WCAG compliant" claims) must extend to every compliance regime the packs cover. The pack labels say "(automated)"; the YAML files, module sources, and finding descriptions never claim a target is _compliant_.

the documentation (Accessibility), §10.4.1 (new — Compliance Packs), §10.7
(Security), §10.9 (LLM audit), §17 (Configuration), §32 (Build order),
our engineering rules(no aggressive scanning), §28 (Accessibility wording rule
extended to every regime), §32 (Error handling — typed compliance
failures), §38 (Report rules — answer the auditor's question) frame
the work.

## Decision

ships **five** deliverables under a single ADR:

1. **`Finding.compliance_id` field** (additive, no schema bump). Optional, regex `^[a-z][a-z0-9.-]*:[A-Za-z0-9][A-Za-z0-9._/-]*$`. Encodes the regime + rule id in one string: `wcag-2.2:target-size-min`, `gdpr:Art.6`, `gdpr:EDPB-03/2022`, `ccpa:do-not-sell-link`, `soc2:trail-incomplete`.'s precedent ("re-use's v2 taxonomy fields — no schema bump for additive extensions") is honored: `FINDINGS_SCHEMA_VERSION` stays at `"2"`.

2. **WCAG 2.2 deterministic checks** in `modules/accessibility/checks/wcag22.py` covering five SCs: - `2.4.11` Focus Not Obscured (Minimum) — bounding-box overlap between focusable elements and sticky / fixed overlays. - `2.5.7` Dragging Movements — drag-only UI (`cursor: grab`, `draggable=true`) with no documented keyboard alternative. - `2.5.8` Target Size (Minimum) — clickable elements smaller than 24 × 24 CSS px (inline-link and UA-default-styling exceptions honored). - `3.3.7` Redundant Entry — same logical field asked for twice across steps (heuristic: `purpose` → `autocomplete` → `name` → `label`). - `3.3.8` Accessible Authentication (Minimum) — cognitive function test (CAPTCHA puzzle) with no documented alternative. The accessibility default `axe.tags` is extended to `("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa",
"best-practice")` (axe-core 4.10+).

3. **New compliance module** at `modules/compliance/` shipping four sub-checks (`gdpr`, `ccpa`, `soc2_trail`, `wcag22`): - `gdpr.py` — consent banner detection, cookies-before-consent (Art. 6), asymmetric reject UX (EDPB 03/2022). - `ccpa.py` — Do Not Sell / Share link presence + opt-out form verification. - `soc2_trail.py` — seven-gate audit on SentinelQA's own `audit.log`: existence, JSONL parseability, monotonic timestamps, presence of safety decisions, paired module-start / module-end events, artifact events, and absence of unredacted secrets (Bearer tokens, JWTs, sk-/AKIA keys, Set-Cookie values). Optional gates for LLM events and vault events. - `wcag22_check.py` — signal-driven adapter that invokes the deterministic checks against `<run-dir>/compliance/signals/wcag22.json`. The module follows the standard SentinelModule lifecycle, reads optional signal files (missing → check skips with `signals_seen=False` per the engineering guidelines), and writes per-check summaries to `<run-dir>/compliance/{gdpr,ccpa,soc2_trail,wcag22}.json` plus `<run-dir>/compliance/index.json` listing what ran.

4. **Compliance pack DSL** in `engine/policy/compliance.py`: - Strict Pydantic model (`extra="forbid"`). - `CompliancePack`: `id` (lower-kebab), `label`, `description`, `version`, `includes` (list of `PackInclude`), `fail_on`, `warn_on`. - `PackInclude`: `module`, free-form `options`, `checks` filter. - Loader resolves built-in pack ids against `policy/compliance/` OR a filesystem path. - Validation runs at **load time** — unknown modules, unknown check ids, and checks against modules that don't support the filter all fail before any run starts. - Pack composition: repeated entries per module are allowed; the loader merges `options:` (last-wins) and unions `checks:` into a final `enabled_checks` tuple threaded into the module via `ctx.options`.

5. **Four built-in packs** under `policy/compliance/`: - `wcag-2.2-aa.yaml` — runs accessibility (axe WCAG 2.2 tags) + compliance (`wcag22` check). - `gdpr-baseline.yaml` — runs compliance (`gdpr` check, with `flag_missing_consent_banner: true`). - `ccpa-baseline.yaml` — runs compliance (`ccpa` check, with `enforce_ccpa_link_presence: true`). - `soc2-trail.yaml` — runs compliance (`soc2_trail` check only). Every pack label ends with "(automated)". The wording guard `tests/security/test_no_compliance_claims.py` greps the compliance module sources + pack YAMLs + `engine/policy/compliance.py` for 14 forbidden phrases ("WCAG compliant", "GDPR compliant", "CCPA compliant", "SOC 2 compliant", "fully X compliant", etc.).

The CLI gains `sentinel audit --compliance-pack <id-or-path>`:

- Resolves the pack via `engine.policy.compliance.load_compliance_pack`.
- Threads `pack.requested_modules` into the lifecycle's `requested_modules` and `pack.module_options` into `module_options`.
- Returns `EXIT_CONFIG_ERROR` (2) on pack-load failure.
- In `--json` mode, emits `compliance_pack: <id>` on the response payload.

## Consequences

- Operators get a one-flag posture: `sentinel audit --compliance-pack
wcag-2.2-aa`. Custom packs ride the same flag.
- The compliance module is independently runnable (no pack needed) via `sentinel audit --modules compliance` plus the per-check options. Pack DSL is the polished UX, not the only path.
- `Finding.compliance_id` joins `cwe_id`, `attack_id`, `owasp_api_id` as a fourth additive taxonomy field. Schema version stays at `"2"` per the precedent.
- SOC 2 trail audit is **about SentinelQA's own runs**, not about the target product. The audit log itself is the artefact; the gates surface defects in the audit-log writer.
- WCAG 2.2 deterministic checks run when signal data is present in `<run-dir>/compliance/signals/wcag22.json`. Population of those signals from a live browser is a runtime concern ( / visual extension); the module handles missing signals gracefully (the engineering guidelines— no fake findings, no fake passes).

## Alternatives considered

1. **Bump `FINDINGS_SCHEMA_VERSION` to `"3"`** for `compliance_id`. Rejected: the phase summary already established that additive optional taxonomy fields do NOT require a bump (`FINDINGS_SCHEMA_VERSION` rule per `engine/domain/schema.py` docstring).'s bump was justified by adding three fields _and_ a migration helper; adds one field with the same default-None pattern and lives at v2.

2. **Make the compliance module a plugin under.** Rejected: the four sub-checks are first-class — they need typed inputs / outputs, real findings, and stable wire formats. The plugin architecture is the right fit for _third-party_ compliance regimes (HIPAA shape, PCI-DSS shape) once the base packs land.

3. **Run the SOC 2 trail audit as a lifecycle hook (not a module).** Rejected: hooks bypass quality scoring + report emission. Treating SOC 2 trail audit as a module sub-check keeps it inside the normal pipeline so its findings appear in `findings.json`, `report.html`, JUnit, and SARIF outputs.

4. **Build the runtime path for WCAG 2.2 signal capture in.** Rejected — out of scope. ships the deterministic check functions, the compliance-module integration, and the signals schema; populating signals from a live browser belongs in a follow-up that extends the TS audit pipeline. The compliance module skips gracefully when signals are absent.

## References

- the documentation.1 (Compliance Packs — new section).
- the documentation (Configuration — `policy.compliance` block).
- our engineering rules(Accessibility wording rule, extended to every regime).
- our engineering rules(Error handling — typed compliance failures).
- our engineering rules(Report rules — answers the auditor's question).
- WCAG 2.2 — https://www.w3.org/TR/WCAG22/
- EDPB Guidelines 03/2022 on dark patterns — https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-032022-deceptive-design-patterns-social-media_en
