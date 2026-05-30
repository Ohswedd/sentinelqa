# Task 35.03 — License headers + NOTICE audit

## Deliverables

- New script `scripts/release/audit_license_headers.py` walks every
  Python (`.py`) and TypeScript (`.ts` / `.tsx`) file under `engine/`,
  `apps/`, `modules/`, `integrations/`, `packages/`, `scripts/`,
  `tests/`. For each file:
  - If the file declares `SPDX-License-Identifier: Apache-2.0` in the
    first 30 lines, pass.
  - Else if the file is under one of the documented covered
    directories (root `LICENSE` applies), pass.
  - Else fail with "missing SPDX header".
- `make audit-license-headers` runs the script in CI mode.
- For files flagged missing, add the standard header:
  ```python
  # SPDX-License-Identifier: Apache-2.0
  # Copyright (c) 2026 SentinelQA contributors.
  ```
  (or the TS equivalent).
- `NOTICE` updated: list every third-party dependency vendored in the
  repo (`packages/shared-schema/external/`, `node_modules/` aren't
  vendored at the source level — only schemas; list each schema's
  upstream + license).

## Tests required

- `tests/integration/release/test_license_headers.py` — runs the
  audit script in `--check` mode; fails CI on a missing header.
- `tests/integration/release/test_notice_complete.py` — every entry
  in `packages/shared-schema/external/` has a corresponding NOTICE
  entry.

## Definition of Done

- [ ] Audit script ships; `make audit-license-headers` green on
      `main`.
- [ ] NOTICE lists every vendored upstream schema with its license +
      source URL.
- [ ] `STATUS.md` updated.
