# Task 33.06 — License audit (SPDX)

## Deliverables

- `modules/supply_chain/licenses.py`. Reads the SBOM; for each
  component:
  - Resolve declared license via the lockfile (npm `license` field,
    Python `Classifier: License :: ...`, PyPI metadata).
  - For unknown / missing license, emit finding `license-unknown`
    (CWE-1059 documentation gap; `severity: low`).
  - For known-bad combos (e.g. AGPL-3.0 in an Apache-2.0 product):
    finding `license-conflict` (`severity: high`).
- Configurable allowlist/denylist in `policy.supply_chain.licenses`:
  ```yaml
  policy:
    supply_chain:
      licenses:
        allow: [Apache-2.0, MIT, BSD-3-Clause, BSD-2-Clause, ISC, Python-2.0]
        deny: [GPL-3.0-only, AGPL-3.0-only, AGPL-3.0-or-later]
        unknown_severity: low      # info | low | medium | high
  ```
- Output `<run_dir>/supply_chain/licenses.json` carries the matrix:
  per-component license + verdict + recommendation.

## Tests required

- `tests/unit/modules/supply_chain/test_license_resolver.py` —
  fixture covers each package shape (npm / pypi / orphan).
- `tests/unit/modules/supply_chain/test_license_policy.py` — allow /
  deny / unknown branches.

## Definition of Done

- [ ] Allow / deny defaults documented.
- [ ] Findings carry SPDX ids.
- [ ] `STATUS.md` updated.
