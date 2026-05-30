# Task 33.07 — `sentinel supply-chain` CLI + config polish

## Deliverables

- `apps/cli/src/sentinel_cli/commands/supply_chain_cmd.py` — replaces
  the Phase 02 stub. Subcommand surface:
  - `sentinel supply-chain` — runs the full module pipeline (SBOM,
    OSV, freshness, postinstall, container, licenses) and emits
    findings.
  - `sentinel supply-chain sbom --out <path>` — emit SBOM only.
  - `sentinel supply-chain osv --sbom <path>` — OSV lookup against an
    existing SBOM file.
- New top-level config block in `engine/config/schema.py`:
  ```yaml
  policy:
    supply_chain:
      max_lockfile_age_days: 180
      osv:
        enabled: true
        api_base: https://api.osv.dev
      container:
        image: null
        max_findings: 200
      licenses:
        allow: [...]
        deny: [...]
  ```
- Module wiring under `engine.modules.SUPPLY_CHAIN` so the run
  lifecycle treats it like any other module (Phase 10's contract).

## Tests required

- `tests/integration/cli/test_supply_chain_cmd.py` — every
  sub-surface, every exit code (0 / 1 / 2 / 4 / 5).
- `tests/unit/config/test_supply_chain_block.py` — strict validation.

## Definition of Done

- [ ] CLI replaces the Phase 02 stub.
- [ ] Default config is "everything on but conservative thresholds".
- [ ] `sentinel.config.yaml.example` documents the block.
- [ ] `STATUS.md` updated.
