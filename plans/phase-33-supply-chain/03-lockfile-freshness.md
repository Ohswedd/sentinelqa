# Task 33.03 — Lockfile freshness + integrity check

## Deliverables

- `modules/supply_chain/freshness.py`:
  - For each lockfile, compute `age_days = today - max(file_mtime,
    last_git_commit_touching_it)` (git-aware so the check still works
    on a fresh clone).
  - Flag any lockfile older than
    `policy.supply_chain.max_lockfile_age_days` (default 180);
    `severity: medium`.
  - Verify lockfile <-> manifest consistency: for `package-lock.json`
    + `pnpm-lock.yaml`, assert every direct dep in `package.json`
    appears in the lockfile and pins a single resolved version.
    Drift → `severity: medium`.
  - For Python: `uv.lock` / `poetry.lock` checked against
    `pyproject.toml` dependency declarations.

## Tests required

- `tests/unit/modules/supply_chain/test_freshness_age.py` — synthetic
  mtimes; default + override threshold.
- `tests/unit/modules/supply_chain/test_lockfile_manifest_drift.py` —
  fixtures with drifted lockfiles.

## Definition of Done

- [ ] Findings carry `cwe_id: CWE-1357` (Reliance on Unmaintained
      Third-Party Components).
- [ ] No false positive on the Phase 26 examples.
- [ ] `STATUS.md` updated.
