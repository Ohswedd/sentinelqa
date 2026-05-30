# Phase 33 — Supply-Chain & Dependency Audit

## Objective

Today SentinelQA audits the **running** app (the surface in PRD §10).
Phase 33 adds an audit of the app's **supply chain** — what was used to
build it, what known CVEs apply, what licenses are in the bundle, and
whether the package install hooks are doing anything sketchy. This is
release-confidence's other half: a clean run against a runtime that ships
with a poisoned dependency is still a regression.

All checks are **defensive / read-only**. No active exploitation, no
network calls against attacker-controlled hosts. The OSV lookup is a
read-only query against the public OSV database (`api.osv.dev`), with
graceful offline degradation.

## PRD / CLAUDE.md references

- PRD §10.7 (Security), §22 (Plugin architecture — could host
  third-party scanners as plugins later), §32 (Recommended build order
  — supply-chain belongs after the core modules stabilise).
- CLAUDE.md §6 (no aggressive scanning), §26 (Security module rules),
  §35 (Dependency rules).

## Sub-phases & tasks

1. `01-sbom-cyclonedx.md` — Generate CycloneDX 1.5 SBOM for the
   target's Python + Node lockfiles. Stored under `<run_dir>/sbom/`.
2. `02-osv-lookup.md` — Query OSV for every package@version in the
   SBOM; build a `vulnerabilities.json` report; fail at configurable
   severity floor.
3. `03-lockfile-freshness.md` — Detect lockfiles older than
   `policy.supply_chain.max_lockfile_age_days` (default 180).
4. `04-postinstall-scanner.md` — Parse `package.json` / `setup.py`
   for postinstall hooks; flag scripts that touch the network or the
   filesystem outside the package dir.
5. `05-container-scanner.md` — Adapter for Trivy / Grype (optional
   external binary; falls back to "skipped" when not installed). Runs
   read-only against the configured container image; results
   normalised into the same finding shape.
6. `06-license-audit.md` — SPDX license extraction; fail on
   GPL-on-Apache surface, on unknown licenses, on missing LICENSE
   files in vendored deps.
7. `07-cli-and-config.md` — `sentinel supply-chain` command; config
   block; module wiring.

## Definition of Done

- Every check ships as a `modules.supply_chain.*` module.
- Findings re-use the standard Phase 03 shape + the new CWE / OWASP
  tags from Phase 32.09.
- OSV lookup respects `target.rate_limit_rps`; gracefully degrades
  offline.
- ADR-0045 (Supply-chain module) accepted.
- PRD §10.7.2 (new sub-section) documents the module.
- Coverage gate met (`modules/supply_chain` ≥ 85 %).

## Phase Gate Review

- [ ] Six checks ship.
- [ ] CycloneDX SBOM validates against the official 1.5 schema.
- [ ] OSV / container scanner safely degrade offline.
- [ ] License audit catches GPL contamination on a synthetic fixture.
- [ ] ADR-0045 accepted.
- [ ] PRD updated.
- [ ] `STATUS.md` updated.
