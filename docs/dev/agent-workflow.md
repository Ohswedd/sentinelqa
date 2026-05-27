# Agent workflow (LLM coding assistants)

Status: `Stable`

This doc is the playbook for an LLM coding agent (Claude Code, Cursor, Aider, Devin, etc.) working on SentinelQA. Human contributors should read this too — it explains how agents are expected to behave so reviewers know what to push back on.

## The driving prompt

The canonical prompt for advancing SentinelQA one phase at a time lives at [`plans/PROMT.md`](../../plans/PROMT.md). It's the literal text a human (or another orchestrator) pastes into the agent at the start of each session. The prompt enforces:

1. Read `plans/README.md`, `plans/STATUS.md`, the active phase folder, and the PRD/CLAUDE sections that govern that phase.
2. Audit the previous phase before starting a new one (re-run gates; confirm the gate-review row; confirm the deferred-scope register is empty).
3. Branch as `feature/phase-<NN>-<short-slug>` off `main` unless `STATUS.md` already names a branch.
4. Execute every task in the active phase, in the order listed in the phase README. Each task = its own Conventional Commit.
5. Run `make ci` before every commit.
6. Update `STATUS.md` after every task.
7. At the end of the phase, run the Phase Gate Review documented in the phase README. Stop. Output a summary. Wait for re-prompt.

## Authority order (CLAUDE.md §2)

Agents follow the same authority order as humans:

1. System / developer safety rules.
2. User instructions.
3. `CLAUDE.md` (the engineering constitution).
4. `PRD.md` (the product source of truth).
5. ADRs under `docs/adr/`.
6. Inline comments.
7. `plans/` (execution plan).

If the active task in `plans/` contradicts `CLAUDE.md` or `PRD.md`, the agent must stop, surface the conflict, and update `plans/` (or the PRD/CLAUDE.md, if those are the side that needs to change) **before** continuing.

## Non-negotiables

These are the hard rules an agent must enforce on itself:

- **No stealth / evasion / unauthorized targets / destructive defaults** (`CLAUDE.md` §6, PRD §2). Refuse the task. Update `plans/` and PRD if the spec is at fault.
- **No fake completion** (`CLAUDE.md` §37). No hardcoded scores, no empty returns dressed as success, no `TODO`s without tracked issues, no weakened tests to force CI green.
- **No `Co-authored-by:` trailers for the agent itself** (`CLAUDE.md` §3). Git author + committer must be the human owner's identity. CI workflow `no-ai-coauthor.yml` enforces this.
- **No bypassing pre-commit hooks** with `--no-verify` unless explicitly authorized in that conversation by the user.
- **Update `PRD.md` in the same branch** as any change to behavior, CLI/SDK contract, lifecycle, safety boundary, report schema, data model, or scoring (`CLAUDE.md` §5).
- **Update `STATUS.md` after every task** (mark complete, advance pointer). The pointer is the only source of truth for "where are we?".
- **One Conventional Commit per logical unit of work.** No squashing tasks together; no commits that mix unrelated changes.

## What the agent owns vs. what it surfaces

Owns:

- Code, tests, ADRs, docs, schemas, configs, and lockfiles within the scope of the active phase.
- Running `make ci` and fixing whatever it surfaces.
- Updating `STATUS.md`, the PRD, ADRs, and the CHANGELOG when the work justifies it.

Surfaces to the user (does not act unilaterally):

- Risky / hard-to-reverse actions: `git push --force` to `main`, deleting branches, dropping schemas, removing dependencies, modifying CI in ways that bypass gates.
- Public actions: opening PRs against a public remote, posting to Slack/issues/etc., uploading to PyPI/npm.
- Ambiguous spec interpretations where the PRD or CLAUDE.md are silent or contradictory.
- Anything the agent cannot safely complete inside the active phase. Do NOT silently defer to a future phase — surface it in the gate review.

## What the agent must not do

- Commit secrets, credentials, real customer data, or `.env` files (`CLAUDE.md` §33). The gitleaks pre-commit hook is the backstop, not the policy.
- Modify `PRD.md` or `CLAUDE.md` to make a failing rule pass.
- Add AI tools to `CODEOWNERS`, package maintainers, or commit trailers.
- Force-push to `main`. Force-push to a feature branch is allowed if the branch is unshared.
- Run external scanners / actions against any URL that is not on the configured allowlist.
- Skip the phase gate review at the end of a phase. The gate is hard.

## End-of-phase output

When the gate review passes, the agent's final message to the user must contain:

1. **What shipped** in this phase, in a few bullets.
2. **Gate review verdict** (PASSED / PASSED with deferred verifications / FAILED) and a one-line reason.
3. **Next active pointer** — exact phase, sub-phase, and task file the next session should start with.
4. **Risks or follow-ups** the user should know about before re-prompting.

If anything blocked the phase (ambiguous PRD, missing approval for a risky action, dependency that can't be installed, a deferred-scope item that the plan didn't anticipate), the agent surfaces that instead of declaring victory.

## Failure modes to watch for

- **Drifting from the plan.** If the active task says "do A" and the agent does "A plus a refactor that touches three other modules", the gate is wrong even if `make ci` is green. Stick to the task scope; raise scope changes as separate PRs.
- **Trusting prior plan text without checking the PRD.** Plans become stale. Always cross-check against `PRD.md` and `CLAUDE.md` before treating a plan instruction as authoritative.
- **Hiding deferred work in the gate-review notes.** If something genuinely cannot finish in the phase, the phase is not done — it goes back to the user with the blocker named.
- **Silent `--no-verify`.** Always surface a hook failure to the user; never silence it.
