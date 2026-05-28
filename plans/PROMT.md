# SentinelQA — Execution Loop Prompt

This file contains the **copy/paste prompt** you give Claude Code (or any AI coding agent) to advance SentinelQA by exactly one phase. After each run, the agent stops at the phase gate, reports its review, and waits for you to paste the prompt again to start the next phase.

Two hard rules this loop enforces, on every phase, without exception:

1. **No deferred scope.** "Risks", "follow-ups", "Phase X will handle this later", `TODO`s, env-var-gated capabilities, or known coverage/holes are all deferred scope. If something genuinely belongs in a later phase, it must already be a task in that phase's folder. Otherwise it must be **finished inside the current phase** or formally **removed from scope** via an ADR signed in `STATUS.md`. Closing a phase with un-rehomed risks is forbidden.
2. **Push, CI-watch, and merge-to-main are part of closing the phase.** The agent pushes the branch, opens or updates the PR, waits for every required check to go green, fixes failures, and merges to `main` (squash, branch deleted). You should not be running `git push`, `gh pr create`, `gh pr checks`, or `gh pr merge` by hand. The PR URL + merge commit SHA + CI run URL are recorded in `STATUS.md` before the phase is signed off.

---

## How to use

1. Open the repo in Claude Code at `/Users/ohswedd/Desktop/SENTINEL QA` (or wherever the repo lives). Make sure `gh auth status` is green; the agent will use `gh` to push, watch checks, and merge.
2. Copy the prompt block below — **everything between the `BEGIN PROMPT` and `END PROMPT` markers**.
3. Paste it as your message. The agent will:
   - read `plans/STATUS.md` to find the active phase,
   - read the phase's `README.md` and every task file in the folder,
   - verify the prior phase actually closed cleanly (gates green, deferred-scope register empty, merged to `main`),
   - execute every task in the active phase to true completion (no risks, no follow-ups, no later-phase punts),
   - run the phase gate review,
   - push the branch, open/update the PR, wait for CI to go green, fix any failures, merge to `main`, delete the remote branch,
   - update `STATUS.md` with the PR URL, CI run URL, and merge commit SHA,
   - **stop** with a tight summary.
4. Inspect what was done. When you are satisfied, paste the same prompt again to start the next phase.

If the agent ever surfaces a "risk", "follow-up", or "Phase X will…" item in its end-of-phase summary, **do not advance** — reply with `Resolve the gaps you reported before proceeding.` and the agent will treat that item as in-scope work for the current phase.

---

## BEGIN PROMPT

You are continuing the SentinelQA build. The plan is authoritative and lives in `plans/`. Follow `CLAUDE.md` exactly. Follow `PRD.md` exactly. If they conflict with each other or with `plans/`, stop, resolve the conflict in the docs first, then continue.

You have **standing authorization** for this project to:

- Push branches to the configured GitHub remote.
- Create and update pull requests via `gh`.
- Wait on / inspect CI checks via `gh pr checks` and `gh run view`.
- Merge the PR to `main` once every required check is green, using `gh pr merge --squash --delete-branch`.
- Fetch and fast-forward `main` after the merge.

You do **not** have authorization to: force-push to `main`, use admin/bypass merge flags, skip checks (`--admin`, `--no-verify`, etc.), or merge while any required check is red, queued, or pending.

Do this loop, in order:

1. **Orient.** Read `plans/README.md`, `plans/STATUS.md`, and the phase folder pointed to by `STATUS.md`'s "Active pointer". Read every task file in that phase folder, and re-read the `PRD.md` and `CLAUDE.md` sections the phase README cites. `git fetch --all --prune`. Confirm `gh auth status` is green.

2. **Verify the prior phase actually closed.** Before doing any new work:
   - Confirm `STATUS.md` has a signed gate-review row for every phase marked `[x]`, including PR URL and merge commit SHA in the PR & merge log.
   - Confirm `git log origin/main` contains the prior phase's merge commit. If a prior phase is marked done but never merged to `main` — that phase is **not** done. Stop and finish it (push, watch CI, merge) before touching the new phase.
   - Confirm the deferred-scope register is empty.
   - Re-run the prior phase's quality gates (format, lint, typecheck, unit/integration/CLI/security/schema tests per `CLAUDE.md` §17). If they fail, stop and fix before starting new work.
   - Confirm `PRD.md` and `CLAUDE.md` reflect the prior phase's behavior, schemas, and boundaries.

3. **Branch.** From an up-to-date `main` (`git checkout main && git pull --ff-only origin main`), create the phase branch `feature/phase-<NN>-<short-slug>` unless `STATUS.md` already names one. Never work directly on `main`.

4. **Execute every task in the active phase, in the order listed in the phase README.** For each task:
   - Open the task file and follow its detailed steps.
   - Honor the safety boundary in `CLAUDE.md` §6 and PRD §2. No stealth, evasion, unauthorized targets, or destructive defaults — ever.
   - Write tests as the task file specifies (unit, integration, CLI, schema/golden, security policy, report). No feature is complete without tests (`CLAUDE.md` §16).
   - Update `PRD.md` whenever you change product behavior, CLI/SDK contract, lifecycle, safety boundary, report schema, data model, scoring, or roadmap (`CLAUDE.md` §5). Update `CLAUDE.md` only if a project-wide engineering rule actually changed.
   - Write or update the relevant ADR for any architectural decision listed in `CLAUDE.md` §34.
   - Run quality gates from `CLAUDE.md` §17 locally before committing.
   - Commit with Conventional Commits. **Do not** add `Co-authored-by:` for AI tools. Do not add AI as a maintainer or owner (`CLAUDE.md` §3).
   - Update `STATUS.md`: mark the task done and advance the pointer.

5. **No fake completion. No deferred scope.** Forbidden, regardless of how it's phrased:
   - Hardcoded scores, empty returns dressed as success, untracked `TODO`s, placeholder modules pretending to work, weakened tests to force green (`CLAUDE.md` §23, §37).
   - "Risks", "follow-ups", "known gaps", "we should also…", "Phase X will…", "out of scope (will be wired later)", `xfail`/`skip` without an expiry, env-var-gated capabilities that are required by the phase's PRD section, coverage exclusions, brittle workarounds left in place — all of these are **deferred scope** when they originate in this phase.

   Before declaring the phase done, sweep your own work-in-progress notes and resolve every such item by one of:
   - **Finish it now** in this phase (preferred default). Add a task file in the current phase folder if it's missing one; execute it; commit.
   - **Re-home it explicitly** to a later phase. The item must already be a named task in that phase's folder (with detailed deliverables), AND `STATUS.md` must record the re-home with the rationale. "Phase 17 will handle X" without an existing task file in Phase 17 is not re-homing — it is hand-waving.
   - **Remove it from scope** via an ADR. Write the ADR, get it Accepted, link from `PRD.md`, and update `STATUS.md`. Out-of-scope items never appear in the phase summary as risks; they appear as Accepted ADRs.

   If you catch yourself about to write "follow-up:" or "Phase 17 needs to…" in your summary, that is the signal to go back and finish the work, re-home it with a real task file, or write the ADR.

6. **Phase Gate Review.** When every task is complete, run the gates listed in the phase README plus these universal gates:
   - All tests pass (unit, integration, CLI smoke if CLI changed, schema/report if outputs changed, security policy if scanning changed).
   - Lint, format, typecheck clean for every package this phase touched.
   - Coverage gates from the phase README met (both package-level and per-file where the phase requires it). Coverage gaps below the floor are not "follow-ups"; they are failures.
   - `PRD.md` reflects current behavior; ADRs exist for every CLAUDE §34 trigger reached this phase.
   - Deferred-scope register in `STATUS.md` is empty.
   - No secrets, tokens, real credentials, or AI-co-author trailers committed (`CLAUDE.md` §3, §33).
   - `git status` clean.

7. **Close out the phase: push → PR → CI → merge.** This is part of closing the phase, not a separate manual step:

   a. `git push -u origin feature/phase-<NN>-<slug>`.

   b. Find or create the PR with `gh pr view --json url,number 2>/dev/null || gh pr create`. Title: `phase <NN>: <short summary>`. Body must include: phase summary (bullet per task), the gate-review verdict, the local `make ci` result, links to ADRs added, and an explicit `Deferred scope: none` line. Use `gh pr create --base main --head feature/phase-<NN>-<slug> --title "…" --body-file <tempfile>`.

   c. Watch checks: `gh pr checks <num> --watch --interval 15`. Read failure logs with `gh run view --log-failed <run-id>`. If anything is red:
      - Diagnose root cause; do not bypass or `--admin` merge.
      - Fix in code on the same branch; commit with a Conventional Commit; push.
      - Re-watch checks. Up to **3** fix attempts. If still red after 3, stop and report the exact failing check + your analysis; do not merge.

   d. With every required check green, merge: `gh pr merge <num> --squash --delete-branch`. The squash commit message uses the phase title and lists the per-task commits in the body (extract via `git log feature/phase-<NN>-<slug> --not main --reverse --format="- %s"`).

   e. Sync local main: `git checkout main && git pull --ff-only origin main`. Confirm the merge commit is present (`git log -1 --format="%H %s"`).

   f. Update `STATUS.md`:
      - Flip the phase progress checkbox to `[x]`.
      - Fill in the gate-review row: status `done`, verdict `PASS`, your reviewer name (the human owner from `CODEOWNERS`), today's date, Notes including the local `make ci` summary.
      - Add a row to the **PR & merge log** with: phase number, branch, PR URL, the CI run URL (the run that turned the PR green), merge commit SHA, merge date.
      - If you updated `PRD.md` or `CLAUDE.md`, add a row to the sync log.
      - Advance the **Active pointer** to the next phase and its first task.
   Commit the `STATUS.md` update directly to `main` with a `docs(status): close phase <NN>` Conventional Commit, then `git push origin main`. (The `STATUS.md` post-merge update is the one exception to the "no direct commits on main" rule, and only because it records the merge that just happened.)

8. **Stop at the gate.** Output a short summary, in this exact shape, and **nothing else**:

   - **Shipped in Phase <NN>**: one bullet per task (≤ one line each).
   - **Gate verdict**: PASS / FAIL.
   - **CI**: PR URL · CI run URL · merge commit SHA · branch deleted.
   - **Docs touched**: list of files (PRD/CLAUDE/ADRs/STATUS).
   - **Deferred scope**: `none` (literally — if you cannot truthfully write `none`, you are not done; go back to step 5).
   - **Next active pointer**: phase / sub-phase / task file.

   Then stop. Do not start the next phase. Wait for the user to re-paste this prompt.

If at any point you cannot proceed safely — ambiguous PRD, missing approval for a risky action, dependency you cannot install, a CI failure you cannot fix in 3 attempts, an unmerged prior phase — stop, explain precisely what is blocking you, and propose the smallest correct fix (usually a task-file or PRD update first, then resume).

The product's purpose is to answer one question with evidence: *Can this software be trusted enough to ship?* (`CLAUDE.md` §45). Build SentinelQA so it can answer that question about itself first.

## END PROMPT

---

## Notes for the user

- The prompt is intentionally **identical every time**. State lives in `plans/STATUS.md`, not in the prompt, so you never need to edit it between runs.
- If you want to skip ahead or rewind, edit the **Active pointer** in `STATUS.md` before pasting the prompt.
- If a phase is very large and you want to break the run, hit `Esc` at any safe point — the agent commits at task boundaries, so you will not lose finished work. Re-paste the prompt and it will resume from the next unfinished task.
- The prompt forbids the agent from advancing past a failing gate, declaring a phase done while CI is red, or reporting deferred work as "risks/follow-ups". If you ever see the loop violate any of those, that is a bug in this file or in a phase README — stop the agent, fix the rule, then resume.
- The default merge strategy is `--squash --delete-branch`. If you prefer rebase or merge commits, change step 7.d above. Each phase becomes one squash commit on `main`; the per-task history remains visible on the merged PR.
- Up-to-3 CI fix attempts is a guardrail, not a target. The expectation is that `make ci` was green before the push, so CI should usually pass on the first try.
