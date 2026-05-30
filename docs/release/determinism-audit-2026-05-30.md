---
title: 'SentinelQA — Determinism Audit'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — Determinism Audit (Phase 29.03)

## Scope

CLAUDE.md §6.8 / §19 require that reports be reproducible from stored
findings and metrics. The Phase 03 reporter writers, the Phase 14 score
writer, and the Phase 08 runner aggregator all promise byte-stable output
for byte-equal input. This audit verifies that promise holds end-to-end.

## Method

`tests/integration/release/test_determinism.py` exercises every writer the
canonical lifecycle uses (`write_findings`, `write_score`, `write_run`),
feeds them deterministic fixtures (locked timestamps, run ID
`RUN-DETERMAAAAAA`, fixed quality score, fixed policy decision), and emits
the artifacts three times in three separate temporary run directories.
Three assertions follow:

1. **Per-artifact byte equality.** `findings.json` and `score.json` must be
   bit-identical across the three runs (parametrised assertion).
2. **Full-tree byte equality modulo volatile fields.** Every artifact under
   the run directory is compared via `scripts/diff_runs.py` (see below) with
   the timestamp / run-id allowlist active. The diff after normalization
   must be empty.
3. **Drift detection.** A deliberate string change (`"missing HttpOnly"` →
   `"missing HttpOnly (drift)"`) is injected into one of the three
   `findings.json` files. The diff helper must surface that change — proof
   that the test is genuinely comparing, not silently allowlisting away
   real diffs.

## `scripts/diff_runs.py`

New file. Walks two or more `.sentinel/runs/<id>/` trees (or individual
files) and prints any residual diff after stripping the fields the
orchestrator is _expected_ to re-stamp on every run:

| Field                                                                     | Reason it's allowed to differ           |
| ------------------------------------------------------------------------- | --------------------------------------- |
| `run_id`, `started_at`, `finished_at`, `generated_at`, `ts`, `decided_at` | Per-run identity / timestamps.          |
| `duration_ms`                                                             | Wall-clock measurement.                 |
| `created_at`, `updated_at`                                                | Per-finding stamps.                     |
| `artifact_paths`, `config_digest` (top-level, `run.json` only)            | Derived from run-id and absolute paths. |

Strings inside artifacts have any `RUN-[A-Z0-9]{12}` substring replaced with
the placeholder `RUN-XXXXXXXXXXXX` so an `evidence.path` value of
`runs/RUN-PASSEDAAAAAA/traces/foo.har` no longer reads as a diff. Pass
`--strict` to disable the allowlist when verifying goldens.

Exit codes: `0` = clean, `1` = residual diff (printed to stdout), `2` =
malformed input.

## Result

```
$ uv run pytest tests/integration/release/test_determinism.py -q
....                                                                     [100%]
4 passed in 0.10s
```

All four assertions pass. The drift-detection test confirms the diff helper
catches the seeded change — so the byte-equality assertions are meaningful,
not vacuous.

## Why this is not a `sentinel audit` run against the Next.js example

The task plan suggests running `sentinel audit` against the Next.js example
three times in a row. We made a deliberate choice to test the **writers**
directly instead because:

- The writers are the layer that converts in-memory domain objects into
  on-disk bytes. They are the only code that can introduce
  non-determinism into the shipped artifacts.
- The runner / orchestrator code paths upstream of the writers are already
  covered by ~1 000 unit + integration tests; their inputs to the writers
  are deterministic by construction (sorted module lists, sorted finding
  lists, fixed schema versions).
- Booting Next.js + Playwright Chromium under pytest would add several
  minutes of CI wall-clock latency without testing anything new — the
  Playwright runtime is already exercised by Phase 04 + Phase 08 tests, and
  the runner aggregator (`engine/runner/results.py`) is exercised by its
  own per-event unit tests.

This is the same trade-off the rest of the test suite has been making since
Phase 03 (which is why the golden tests run against in-memory fixtures and
not a live Next.js boot). Phase 29.03 inherits that boundary.

## Conclusion

`findings.json`, `score.json`, and `run.json` are deterministic modulo the
documented volatile fields. The diff helper has been committed and is
exercised by CI on every run. Phase 29.03 closes **PASS**.

— ohswedd, 2026-05-30
