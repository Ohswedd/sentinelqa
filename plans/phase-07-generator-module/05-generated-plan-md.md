# Task 07.05 — `sentinel.generated.plan.md`

## Objective

Produce a human-readable Markdown summary of the generation pass so reviewers can see what was created and why.

## Deliverables

- `engine/generator/plan_md.py` emitting `tests/sentinel/sentinel.generated.plan.md` (and a copy in the run dir):
  - Counts of generated specs, page-objects, fixtures.
  - Per-flow: name, priority, confidence, test files generated, source (deterministic / llm).
  - Diff vs. previous generation (if a prior plan.md exists in `tests/sentinel/`).
  - "Sentinel markers": clear comment blocks indicating that the files are generated and managed by SentinelQA (per PRD open question 2 / answer).

## Steps

1. Emit Markdown.
2. Compute diff if prior file exists.
3. Add a banner: "Do not edit by hand. Run `sentinel generate` to regenerate."

## Acceptance criteria

- File present after `sentinel generate`.
- Diff section accurate when re-running.

## Tests required

- `tests/golden/generator/test_plan_md.py`.

## PRD / CLAUDE.md references

- PRD §9.3, §31 Open question 2 (recommended answer).
- CLAUDE.md §22.

## Definition of Done

- [ ] Plan Markdown emitted with banner + diff.
- [ ] `STATUS.md` updated.
