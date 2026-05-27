# SentinelQA — Execution Loop Prompt

This file contains the **copy/paste prompt** you give Claude Code (or any AI coding agent) to advance SentinelQA by exactly one phase. After each run, the agent stops at the phase gate, reports its review, and waits for you to paste the prompt again to start the next phase.

---

## How to use

1. Open the repo in Claude Code at `/Users/ohswedd/Desktop/SENTINEL QA` (or wherever the repo lives).
2. Copy the prompt block below — **everything between the `BEGIN PROMPT` and `END PROMPT` markers**.
3. Paste it as your message. The agent will:
   - read `plans/STATUS.md` to find the active phase,
   - read the phase's `README.md` and all of its task files,
   - execute every task in the phase to completion,
   - run the phase gate review,
   - update `STATUS.md`, `PRD.md`, `CLAUDE.md` (only if the rules require), and any ADRs,
   - commit work in Conventional-Commit style on a phase branch,
   - **stop** with a summary that includes the gate-review verdict.
4. Inspect what was done. When you are satisfied, paste the same prompt again to start the next phase.

If the agent reports any deferred scope, fake completion, missing tests, broken gates, or unupdated docs, **do not advance** — instead reply with `Resolve the gaps you reported before proceeding.` and the agent will keep working on the current phase.

---

## BEGIN PROMPT

You are continuing the SentinelQA build. The plan is authoritative and lives in `plans/`. Follow `CLAUDE.md` exactly. Follow `PRD.md` exactly. If they conflict with each other or with `plans/`, stop, resolve the conflict in the docs first, then continue.

Do this loop, in order:

1. **Orient.** Read `plans/README.md`, `plans/STATUS.md`, and the phase folder pointed to by `STATUS.md`'s "Active pointer". Read every task file in that phase folder, and re-read `PRD.md` sections referenced by the phase README. Re-read `CLAUDE.md` sections that govern this phase (every phase README cites them).

2. **Verify prior phases.** Before doing any new work, audit the previous phase's deliverables:
   - Re-run the prior phase's quality gates (format, lint, typecheck, unit/integration/CLI/security/schema tests as applicable per `CLAUDE.md` §17).
   - Confirm `STATUS.md` has a signed gate-review row for every phase marked `[x]`.
   - Confirm the deferred-scope register is empty.
   - Confirm `PRD.md` and `CLAUDE.md` were updated wherever the prior phase changed behavior, schemas, or boundaries.
   - If anything fails, stop the loop and fix it before touching the new phase.

3. **Branch.** Create a phase branch named `feature/phase-<NN>-<short-slug>` off `main` unless `STATUS.md` already names one.

4. **Execute every task in the active phase, in the order listed in the phase README.** For each task:
   - Open the task file and follow its detailed steps.
   - Honor the safety boundary in `CLAUDE.md` §6 and PRD §2. No stealth, evasion, unauthorized targets, or destructive defaults — ever.
   - Write tests as the task file specifies (unit, integration, CLI, schema/golden, security policy, report). No feature is complete without tests (`CLAUDE.md` §16).
   - Update `PRD.md` whenever you change product behavior, CLI/SDK contract, lifecycle, safety boundary, report schema, data model, scoring, or roadmap (`CLAUDE.md` §5). Update `CLAUDE.md` only if a project-wide engineering rule actually changed.
   - Write or update the relevant ADR for any architectural decision listed in `CLAUDE.md` §34.
   - Run quality gates from `CLAUDE.md` §17 locally before committing.
   - Commit with Conventional Commits. **Do not** add `Co-authored-by:` for AI tools. Do not add AI as a maintainer or owner (`CLAUDE.md` §3).
   - Update `STATUS.md`: mark the task done and advance the pointer.

5. **No fake completion.** Forbidden: hardcoded scores, empty returns dressed as success, untracked `TODO`s, placeholder modules pretending to work, weakened tests to force green (`CLAUDE.md` §23, §37). If something cannot truly be finished inside this phase, the phase is not done — surface it in the gate review.

6. **Phase Gate Review.** When every task in the phase is complete, run the gates listed in the phase README. They always include at minimum:
   - All tests pass (unit, integration, CLI smoke if CLI changed, schema/report if outputs changed, security policy if scanning changed).
   - Lint, format, typecheck clean for every package this phase touched.
   - `PRD.md` reflects current behavior; ADRs exist for every CLAUDE §34 trigger reached this phase.
   - `STATUS.md` phase-progress checkbox flips to `[x]`, gate-review row is filled in with verdict and date, deferred-scope register is empty.
   - No secrets, tokens, real credentials, or AI-co-author trailers committed (`CLAUDE.md` §3, §33).
   - `git status` is clean.

7. **Stop at the gate.** When the gate review is recorded, **stop the loop**. Output:
   - A concise summary of what shipped in this phase.
   - The gate-review verdict.
   - The exact next active pointer (phase, sub-phase, task file).
   - Any risks or follow-ups for the user's attention.

Do not start the next phase. Wait for the user to re-paste this prompt.

If at any point you cannot proceed safely — ambiguous PRD, missing approval for a risky action, dependency you cannot install, a deferred-scope item that the plan did not anticipate — stop, explain precisely what is blocking you, and propose the smallest correct fix (which usually means updating the relevant task file or PRD section first).

The product's purpose is to answer one question with evidence: *Can this software be trusted enough to ship?* (`CLAUDE.md` §45). Build SentinelQA so it can answer that question about itself first.

## END PROMPT

---

## Notes for the user

- The prompt is intentionally **identical every time**. State lives in `plans/STATUS.md`, not in the prompt, so you never need to edit it between runs.
- If you want to skip ahead or rewind, edit the **Active pointer** in `STATUS.md` before pasting the prompt.
- If a phase is very large and you want to break the run, hit `Esc` at any safe point — the agent commits at task boundaries, so you will not lose finished work. Re-paste the prompt and it will resume from the next unfinished task.
- The prompt forbids the agent from advancing past a failing gate. If you ever see the loop trying to move to the next phase with red gates, that is a bug in this file or in the phase README — stop the agent, fix the gate, then resume.
