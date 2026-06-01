# Compliance packs

**Status:** Stable (, ADR-0046).

A _compliance pack_ is a YAML document that composes existing
SentinelQA modules + checks under a single regime label (WCAG 2.2 AA,
GDPR baseline, CCPA baseline, SOC 2 trail). Packs give CI/CD pipelines
a one-flag way to run the relevant subset of checks for a given
audit posture, without hand-wiring `--modules` or per-module options.

> **Wording rule (CLAUDE §28).** Pack labels say "(automated)". The
> packs never claim a target is _compliant_ — only that the
> automated checks ran.

## Quick start

Built-in pack ids:

| Pack id         | What it runs                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| `wcag-2.2-aa`   | Accessibility module's axe-core WCAG 2.2 tags **plus** compliance module's WCAG 2.2 deterministic SCs. |
| `gdpr-baseline` | Compliance module's GDPR checks (consent banner, cookies-before-consent, asymmetric reject).           |
| `ccpa-baseline` | Compliance module's CCPA checks (Do Not Sell link presence + opt-out form verification).               |
| `soc2-trail`    | Compliance module's SOC 2 audit-trail gate against SentinelQA's own `audit.log`.                       |

Run any pack with:

```bash
sentinel audit --compliance-pack wcag-2.2-aa
```

Custom packs work the same way; point the flag at a YAML file:

```bash
sentinel audit --compliance-pack./packs/my-app.yaml
```

## Pack schema

```yaml
pack: id: wcag-2.2-aa # lower-kebab; required. label: WCAG 2.2 AA (automated) # human-readable; required. description: >- # optional longer description. Automated WCAG 2.2 AA coverage … version: 1 # integer; required (forward compat). includes: # 1..64 entries; required. - module: accessibility # module name (validated at load). options: # per-module options (free form). axe_tags: [wcag22a, wcag22aa] - module: compliance checks: [wcag22] # named sub-checks (validated). fail_on: # severities that fail the gate. - severity: critical - severity: high warn_on: # severities that warn but don't fail. - severity: medium
```

### Validation rules

The loader is strict (`extra="forbid"`):

- Unknown top-level keys (anywhere in the document) are rejected.
- `includes[].module` must be a known module — see `engine/policy/compliance.py::known_modules`.
- `includes[].checks` must be a known sub-check for the named module — see `engine/policy/compliance.py::known_checks(<module>)`.
- Modules that do not support the `checks` filter must omit it.

These checks happen at load time, so a misspelled module or check id
fails the run before any work starts.

### Composition behavior

Multiple `includes:` entries for the same module are allowed; the
loader merges them:

- `options:` dicts are merged with last-write-wins on key collisions.
- `checks:` tuples are unioned and threaded into the module's `enabled_checks` option.

```yaml
pack: id: merged-pack label: Merged (automated) version: 1 includes: - module: compliance options: flag_missing_consent_banner: true checks: [gdpr] - module: compliance options: enforce_ccpa_link_presence: false checks: [ccpa]
```

The merged compliance module gets:

```python
{ "flag_missing_consent_banner": True, "enforce_ccpa_link_presence": False, "enabled_checks": ("gdpr", "ccpa"),
}
```

## What runs under each pack

### `wcag-2.2-aa`

- accessibility module with axe-core tags: `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22a, wcag22aa, best-practice`.
- compliance module's `wcag22` check, which runs the deterministic WCAG 2.2 SCs (2.4.11 Focus Not Obscured, 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum), 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication (Minimum)) when signal data is present at `<run-dir>/compliance/signals/wcag22.json`.

### `gdpr-baseline`

- compliance module's `gdpr` check, with `flag_missing_consent_banner: true`. Reads `<run-dir>/compliance/signals/gdpr.json` produced by discovery / the TS runtime. Emits `compliance_id: gdpr:Art.6` and `gdpr:EDPB-03/2022` findings.

### `ccpa-baseline`

- compliance module's `ccpa` check, with `enforce_ccpa_link_presence: true`. Reads `<run-dir>/compliance/signals/ccpa.json`. Emits `compliance_id: ccpa:do-not-sell-link` / `ccpa:do-not-sell-opt-out-form` findings.

### `soc2-trail`

- compliance module's `soc2_trail` check, which audits SentinelQA's own `<run-dir>/audit.log` against seven gates (existence, JSONL parseability, monotonic timestamps, presence of safety decisions, paired module start/end events, artifact events, absence of unredacted secrets). Emits `compliance_id: soc2:*` findings tied to gate failures.

## Signal files

The compliance module reads optional signal files written by the
discovery / runner phases. Missing signals → the corresponding
sub-check reports `skipped` (no fake completion per CLAUDE §37).

| Signal file path                           | Consumed by  |
| ------------------------------------------ | ------------ |
| `<run-dir>/compliance/signals/gdpr.json`   | `gdpr`       |
| `<run-dir>/compliance/signals/ccpa.json`   | `ccpa`       |
| `<run-dir>/compliance/signals/wcag22.json` | `wcag22`     |
| `<run-dir>/audit.log` (auto)               | `soc2_trail` |

## Outputs

Each enabled sub-check writes a summary under `<run-dir>/compliance/`:

```
<run-dir>/compliance/ gdpr.json # GdprCheckReport ccpa.json # CcpaCheckReport soc2_trail.json # Soc2CheckReport (gates + per-gate detail) wcag22.json # Wcag22CheckReport index.json # which checks ran + duration_ms
```

Findings are emitted in the normal `findings.json` with `module:
compliance` plus a `compliance_id` tag (e.g. `wcag-2.2:target-size-min`,
`gdpr:Art.6`).

## CLI exit codes

- `0` — pack ran and the quality gate passed.
- `1` — quality gate failed (one of the pack's `fail_on` severities was hit).
- `2` — pack file invalid (`CompliancePackError` — bad YAML, unknown module, unknown check, …).
- `4` — unsafe target (the run never started).
- `6` — module errored — the audit could not complete.
