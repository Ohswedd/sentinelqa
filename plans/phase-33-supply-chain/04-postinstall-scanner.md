# Task 33.04 — Postinstall hook scanner

## Deliverables

- `modules/supply_chain/postinstall.py`:
  - Walk every `package.json` in `node_modules/` and every Python
    package's `setup.py` / `setup.cfg` / `pyproject.toml[build-system]`.
  - For npm: flag `scripts.preinstall` / `postinstall` /
    `prepublishOnly` that contain any of:
    - `curl` / `wget` / `nc` / `ncat` / `bash -c` / `sh -c` / `eval`.
    - Writes outside the package directory (`/etc/`, `/usr/`, `~/`).
    - Reaches to a non-allowlisted host.
  - For Python: flag `setup.py`'s that import `os.system`,
    `subprocess`, `urllib.request`, `requests` at import time.
- Each match becomes a Finding `cwe_id: CWE-506` (Embedded Malicious
  Code), `severity: high` (curl/wget/nc) or `medium` (filesystem
  writes outside pkg).
- Output `<run_dir>/supply_chain/postinstall_findings.json` carries the
  full list + a summary.

## Tests required

- `tests/unit/modules/supply_chain/test_postinstall_npm.py` —
  fixtures for each pattern + clean cases.
- `tests/unit/modules/supply_chain/test_postinstall_python.py` —
  AST-based scan; clean + suspicious fixtures.

## Definition of Done

- [ ] Patterns documented in `docs/dev/supply-chain-checks.md`.
- [ ] Findings reference CWE-506.
- [ ] `STATUS.md` updated.
