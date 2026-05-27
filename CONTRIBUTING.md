# Contributing to SentinelQA

Thank you for working on SentinelQA. This file is the cold-start guide: read it once, then refer back to `CLAUDE.md`, `PRD.md`, and `plans/` for the deep rules.

> **Authority order** (`CLAUDE.md` §2): system safety rules → user instructions → `CLAUDE.md` → `PRD.md` → ADRs → comments → `plans/`. If `CLAUDE.md` and `PRD.md` ever conflict, stop, resolve the conflict in the docs, then continue.

## 0. Before you start

- The repository is **private** until the human owner says otherwise (`CLAUDE.md` §3).
- AI tools may write code, but they are never listed as Git authors, co-authors, owners, or maintainers (`CLAUDE.md` §3). See [`docs/dev/ownership.md`](./docs/dev/ownership.md).
- SentinelQA is for **authorized testing only** — no stealth, no evasion, no unauthorized targets (`CLAUDE.md` §6 / `PRD.md` §2). Every PR is reviewed against the safety boundary.

## 1. Cold-start setup

You need:

- Python 3.11+ (recommended: 3.12).
- Node.js 20+.
- [`uv`](https://docs.astral.sh/uv/) (Python package manager).
- [`pnpm`](https://pnpm.io/) ≥ 9 (TypeScript package manager).

Full details: [`docs/dev/local-setup.md`](./docs/dev/local-setup.md).

Then:

```bash
git clone <your-fork-or-the-canonical-repo>
cd "SENTINEL QA"
make install          # installs Python deps, TS deps, and pre-commit hooks
make ci               # runs format-check + lint + typecheck + tests
```

If `make install` or `make ci` fails on a clean clone, that's a bug — open an issue with the output.

## 2. Find the next thing to do

`plans/STATUS.md` is the live tracker. The **Active pointer** at the top says which phase, sub-phase, and task is active right now. Open that task file and follow it.

The plan is documented in `plans/README.md` (overview) and `plans/PROMT.md` (the prompt that drives the execution loop for agents). See [`docs/dev/agent-workflow.md`](./docs/dev/agent-workflow.md) for the agent-facing playbook.

## 3. Branch, commit, push

Branches:

- Use one of: `feature/`, `fix/`, `docs/`, `refactor/`, `security/`, `ci/`, `chore/`, `test/`, `perf/`, `build/`.
- Phase work uses `feature/phase-<NN>-<short-slug>` (e.g. `feature/phase-00-foundation`).

Commits:

- [Conventional Commits](https://www.conventionalcommits.org/) with the type whitelist from `CLAUDE.md` §4 (enforced by `commitlint` locally + CI).
- No `Co-authored-by:` trailers naming any AI tool (enforced by `.github/workflows/no-ai-coauthor.yml`).

Push:

- The local `pre-push` hook runs `make ci` before any push leaves the laptop. If it fails, fix the gate locally; do **not** `--no-verify`.

Reference docs:

- [`docs/dev/branching.md`](./docs/dev/branching.md) — branch policy + pre-PR checklist.
- [`docs/dev/commits.md`](./docs/dev/commits.md) — Conventional Commits rules + 10 worked examples.
- [`docs/dev/ci-and-branch-protection.md`](./docs/dev/ci-and-branch-protection.md) — what CI checks are required.

## 4. Definition of Done (quoted from CLAUDE.md §18)

A task is done only when:

- Implementation matches PRD.
- Tests exist and pass.
- Types/lint pass where configured.
- Safety implications are reviewed.
- Reports/schemas are updated if affected.
- Docs/PRD are updated if behavior changed.
- No secrets are introduced.
- `git status` is clean after commit.

You'll see this same checklist in the PR template.

## 5. Updating the PRD

`PRD.md` is the product source of truth (`CLAUDE.md` §5). Update it in the **same branch** as any change to:

- Product behavior.
- CLI or SDK contract.
- Module lifecycle.
- Safety boundary.
- Report schema or data model.
- Quality scoring.
- Roadmap.

If your implementation reveals that the PRD is wrong or incomplete, fix the PRD first (or in the same PR), then change the code.

Record the PRD update in `plans/STATUS.md` → "PRD / CLAUDE.md sync log".

## 6. Architecture Decision Records (ADRs)

If you hit any trigger in `CLAUDE.md` §34 (runtime architecture, plugin system, config schema, scoring algorithm, report schema, security policy, agent/MCP design, cloud boundary), you must add an ADR.

- Template: [`docs/adr/_template.md`](./docs/adr/_template.md).
- Filename: `docs/adr/NNNN-kebab-case-title.md` (NNNN = next four-digit number).
- The `scripts/check-adrs.sh` validator is wired into `make ci` — a malformed ADR fails the build.

Read the full procedure: [`docs/adr/README.md`](./docs/adr/README.md).

## 7. Tests

No feature is complete without tests (`CLAUDE.md` §16). The required categories vary by phase; the phase README tells you which apply. At minimum:

- Unit tests for pure-domain logic.
- Integration tests when crossing the Python ↔ TypeScript boundary or the CLI ↔ engine boundary.
- CLI smoke tests when CLI behavior changes.
- Schema/golden tests when an output schema changes.
- Security policy tests when target/scanning behavior changes.

Bug fixes require regression tests unless impossible. If impossible, document why.

## 8. Secret hygiene

- Never commit `.env`, credentials, tokens, or real customer data (`CLAUDE.md` §33).
- `gitleaks` runs locally (pre-commit) and in CI on every PR.
- Full procedure: [`docs/dev/secret-hygiene.md`](./docs/dev/secret-hygiene.md).

## 9. Status labels in docs

Every doc carries one of four status labels at the top: `Planned`, `Experimental`, `Stable`, `Deprecated`. See [`docs/dev/status-labels.md`](./docs/dev/status-labels.md) for definitions and examples.

## 10. Getting help

- Re-read the [`CLAUDE.md`](./CLAUDE.md) section the gate cites — the rule is almost always there.
- Open an issue using the bug-report or feature-request template under `.github/ISSUE_TEMPLATE/`.
- For safety-boundary concerns, tag the issue with `security` and assign to the human owner.

## 11. Reference index

- [`PRD.md`](./PRD.md) — product source of truth.
- [`CLAUDE.md`](./CLAUDE.md) — engineering constitution.
- [`plans/README.md`](./plans/README.md) — 30-phase execution plan overview.
- [`plans/STATUS.md`](./plans/STATUS.md) — live status & active task.
- [`plans/PROMT.md`](./plans/PROMT.md) — agent execution-loop prompt.
- [`docs/README.md`](./docs/README.md) — every doc, one-line description.
- [`docs/adr/README.md`](./docs/adr/README.md) — ADR procedure and index.
- [`docs/dev/local-setup.md`](./docs/dev/local-setup.md) — local dev environment.
- [`docs/dev/branching.md`](./docs/dev/branching.md) — branch policy.
- [`docs/dev/commits.md`](./docs/dev/commits.md) — Conventional Commits rules.
- [`docs/dev/secret-hygiene.md`](./docs/dev/secret-hygiene.md) — secret-handling rules.
- [`docs/dev/ownership.md`](./docs/dev/ownership.md) — ownership + AI-tool policy.
- [`docs/dev/ci-and-branch-protection.md`](./docs/dev/ci-and-branch-protection.md) — required CI checks and branch protection.
- [`docs/dev/status-labels.md`](./docs/dev/status-labels.md) — doc status conventions.
- [`docs/dev/agent-workflow.md`](./docs/dev/agent-workflow.md) — AI-contributor playbook.
