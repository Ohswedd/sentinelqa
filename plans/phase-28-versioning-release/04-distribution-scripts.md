# Task 28.04 — Distribution scripts

## Deliverables

- `make build:all` produces:
  - Python sdist + wheels for `apps/cli` and `packages/python-sdk`.
  - npm tarballs for `packages/ts-runtime` and other TS packages.
  - Docker runner image tagged with the release version.
- `make inspect:all` prints contents of every built artifact for a sanity review (no secrets, no `.git`, no `.env`).
- A `tests/integration/release/test_built_packages.py` test installs the built sdist into a temp venv and runs `sentinel --version`.

## Acceptance criteria

- All build outputs produced and importable.
- No forbidden file inside the tarballs.

## Definition of Done

- [ ] Build + inspection scripts.
- [ ] `STATUS.md` updated.
