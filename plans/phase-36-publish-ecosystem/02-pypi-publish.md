# Task 36.02 — PyPI publish workflow

## Deliverables

- `.github/workflows/publish-pypi.yml`:
  - Trigger: `on: { push: { tags: ["v*"] } }`.
  - Job 1: `build` — runs `make build-all`; uploads `dist/` as an
    artifact.
  - Job 2: `publish` (depends on `build`) — uses
    `pypa/gh-action-pypi-publish@release/v1` with the **Trusted
    Publisher** flow (`id-token: write` permission on the job; no
    long-lived API tokens stored in the repo).
  - Job 3: `verify` — installs each published package from PyPI into
    a fresh venv via `uv pip install --index-strategy unsafe-best-match`
    and runs `sentinel --version`. Fails the workflow on a version
    mismatch.
- `pypi.org` configuration (documented in `docs/release/publish-runbook.md`):
  - Trusted Publisher entry for each package: org `Ohswedd`, repo
    `sentinelqa`, workflow `publish-pypi.yml`, environment `pypi-release`.
  - `pypi-release` GitHub Environment requires manual approval from
    the owner (Settings → Environments).
- `scripts/release/dry_run_pypi.py` — runs `uv build --all-packages`
  + `twine check dist/*` to validate every wheel + sdist meets PyPI
  validation before the tag goes out.

## Tests required

- `tests/integration/release/test_pypi_dry_run.py` — calls
  `scripts/release/dry_run_pypi.py`; expects exit 0 on current `main`.

## Definition of Done

- [ ] Workflow committed.
- [ ] Trusted Publisher documented (owner registers).
- [ ] Dry-run green.
- [ ] `STATUS.md` updated.
