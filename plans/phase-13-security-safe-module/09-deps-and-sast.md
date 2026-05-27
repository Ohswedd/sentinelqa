# Task 13.09 — Dependency & static analysis adapters

## Deliverables

- Adapters that shell out to:
  - `pip-audit` (Python deps).
  - `npm audit --json` (JS deps).
  - `osv-scanner` (multi-language).
  - `semgrep --config auto` (optional SAST; off by default).
- Each adapter normalizes output to SentinelQA `Finding` schema with severity from CVSS or advisory rating.
- Behind config flags: `security.dependency_scanners.<name>: true|false`. Default enable `pip-audit` and `npm audit` if their lockfiles exist; `osv-scanner` opt-in; `semgrep` opt-in.
- Adapters never auto-install themselves; doctor command (Phase 02) reports if they're missing.

## Acceptance criteria

- A vulnerable fixture dependency triggers the expected finding via at least one adapter.
- Missing adapter is reported by doctor, not silently ignored.

## Tests required

- `tests/integration/modules/security/test_dep_scan.py` (uses recorded outputs).
- `tests/integration/modules/security/test_sast_optional.py`.

## PRD / CLAUDE.md references

- PRD §10.7.
- CLAUDE.md §26, §35.

## Definition of Done

- [ ] Adapters implemented and tested.
- [ ] Doctor reports missing tools.
- [ ] `STATUS.md` updated.
