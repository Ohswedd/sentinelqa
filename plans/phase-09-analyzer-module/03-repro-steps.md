# Task 09.03 — Reproduction steps

## Objective

Generate concise, copy-pasteable reproduction steps for every failure.

## Deliverables

- `engine/analyzer/repro.py` exposing `reproduction(failure, test_case) -> list[str]`.
- Steps include:
  1. Open the trace zip path.
  2. Visit the failing route.
  3. Perform the steps that led to failure (extracted from `step.start`/`step.end` events).
  4. Observe the failure (expected vs actual).
- Repro must NOT include secrets — pulls credentials from `*_env` references only.
- Optional: a `--export-repro` flag that writes a `tests/sentinel/repro/<finding-id>.spec.ts` minimal Playwright script that reproduces the failure.

## Steps

1. Build the step extractor.
2. Build the optional spec exporter.
3. Tests.

## Acceptance criteria

- Repro steps for a fixture failure are accurate and reproducible.
- No secrets leaked.

## Tests required

- `tests/unit/analyzer/test_repro.py`.
- `tests/integration/analyzer/test_repro_replay.py` — generated repro replays the failure.

## PRD / CLAUDE.md references

- PRD §9.5, §20.
- CLAUDE.md §24, §33.

## Definition of Done

- [ ] Repro steps generated + replay verified.
- [ ] `STATUS.md` updated.
