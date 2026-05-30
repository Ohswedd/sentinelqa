# Task 33.01 — CycloneDX SBOM generation

## Deliverables

- `modules/supply_chain/sbom.py`. For each detected lockfile in the
  target tree (`uv.lock` / `poetry.lock` / `Pipfile.lock` /
  `requirements.txt` / `package-lock.json` / `pnpm-lock.yaml` /
  `yarn.lock`):
  - Parse the lockfile into a typed component list (`name`,
    `version`, `ecosystem`, `purl`, `licenses` — best-effort).
  - Emit a CycloneDX 1.5 JSON document at `<run_dir>/sbom/<lockfile>.cdx.json`.
  - Aggregate component list at `<run_dir>/sbom/index.json` carrying
    the schema-versioned envelope.
- Vendored CycloneDX 1.5 JSON schema under
  `packages/shared-schema/external/cyclonedx-1.5.json`; schema-drift
  guard re-runs `jsonschema.validate` for every generated SBOM.
- Parsers cover only the lockfile shape (no full resolver
  implementation). When the lockfile is malformed, emit a warning
  finding (`severity: low`) and continue with the other lockfiles.

## Tests required

- `tests/unit/modules/supply_chain/test_sbom_parsers.py` — happy
  fixtures for each lockfile shape.
- `tests/integration/modules/supply_chain/test_sbom_against_examples.py`
  — runs SBOM gen against the Phase 26 example apps; output validates
  against the vendored CycloneDX schema.

## Definition of Done

- [ ] CycloneDX 1.5 output validates.
- [ ] All seven lockfile shapes parse.
- [ ] `STATUS.md` updated.
