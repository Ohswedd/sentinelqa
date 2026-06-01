# Commit message convention

Status: `Stable`

Authority: project engineering rules. Enforcement: `commitlint.config.cjs` invoked by `.pre-commit-config.yaml` at the `commit-msg` stage.

## Format

```
<type>(<scope>): <subject>

<body — optional, explain WHY not WHAT>

<footer — optional, e.g. references or BREAKING CHANGE notes>
```

### Allowed types

`feat`, `fix`, `docs`, `test`, `refactor`, `security`, `ci`, `chore`, `perf`, `build`

Any other type is rejected by `commitlint`.

### Rules

- `type`: lower-case, from the whitelist above, required.
- `scope`: kebab-case, encouraged (e.g. `cli`, `policy`, `discovery`, `tooling`, `repo`). Multi-scope (`(scope1,scope2)`) is allowed.
- `subject`: imperative present tense ("add", not "added"). Don't end with a period. No specific case is forced because of proper nouns like "SentinelQA".
- Header (`type(scope): subject`): max 100 chars.
- Body lines: max 200 chars. Wrap at ~72 in practice for readability.
- Footer: machine-parseable footers like `Refs: the documentation`, `Closes: #42`, or `BREAKING CHANGE: ...`.

### Forbidden footers

- `Co-authored-by: <any AI tool>` — never. CI workflow `no-ai-coauthor.yml` (Phase 00.08) blocks PRs with these.

## Worked examples

Each example below would pass `commitlint`. The selection covers every type in the whitelist plus a few real-world flavors.

### 1. `feat` — new product capability

```
feat(discovery): emit forms inventory with semantic role hints

Discovery now records every <form> with its inferred role (login,
signup, search, payment) plus a confidence score. The forms inventory
feeds the planner so generated login/CRUD tests can target real flows
instead of guessing from labels.

Refs: the documentation
```

### 2. `fix` — bug fix in existing behavior

```
fix(policy): refuse public targets when allowlist is empty

Previously an empty allowlist meant "allow everything", which violates
the documentation and our engineering rules"deny all
non-default" and the CLI prints the policy decision before any module
runs.

Closes: #117
```

### 3. `docs` — documentation-only

```
docs(dev): document the agent execution loop in CONTRIBUTING.md

Adds a step-by-step description of so a fresh agent can
pick up the active phase without re-deriving the loop.
```

### 4. `test` — test-only

```
test(reporter): add golden test for findings.json schema v1

Captures the v1 schema as a fixture so future schema changes must
explicitly update the golden (per our engineering rules).
```

### 5. `refactor` — internal restructuring without behavior change

```
refactor(orchestrator): split run lifecycle into pure stages

Extracts the load/validate/resolve/safety steps into pure functions on
RunPipeline so each stage is independently testable. No external
behavior change; existing CLI tests still pass.
```

### 6. `security` — safety / hardening

```
security(repo): block staged commits containing private-key blocks

Adds the detect-private-key pre-commit hook to .pre-commit-config.yaml
on top of gitleaks. Verified locally: a file containing the OpenSSH
private-key header block is rejected even when the surrounding file
extension is .txt.

Refs: our engineering rules§23.1
```

### 7. `ci` — CI workflow change

```
ci(workflows): cache pnpm store between runs

Cuts cold-cache install time from ~45s to ~9s on ubuntu-latest. No
behavior change; only the cache key is new.
```

### 8. `chore` — repo hygiene / configs

```
chore(tooling): bump ruff to 0.8 and re-lock

Pin only — no rule changes. Re-runs format/lint/typecheck/tests; all
green.
```

### 9. `perf` — performance with a measurable target

```
perf(discovery): cap crawler concurrency at 4 to stay under budget

Brings discovery on the FastAPI example from p95 ~8.4s to p95 ~3.2s
while keeping coverage equivalent (verified with the Phase 05 perf
gate).

Refs: the documentation
```

### 10. `build` — build system / packaging

```
build(python-sdk): switch to hatchling for reproducible wheels

Replaces the implicit setuptools backend with hatchling and includes
py.typed in the wheel so downstream type-checkers pick up the SDK
types out of the box.
```

## What gets rejected by commitlint

These will all fail the commit-msg hook:

- `fixed login bug` (no type)
- `feature(cli): add init command` (`feature` not in whitelist; use `feat`)
- `Feat(cli): add init` (type must be lower-case)
- `feat(cli): added init command.` (past tense + trailing period — style preferences flagged by review; the period is the part `commitlint` enforces if `subject-full-stop` is configured)
- `chore: ` (empty subject)
- A 180-char header (over `header-max-length`)

If you ever need to bypass commitlint locally (you very rarely do), `--no-verify` is forbidden by our engineering rules
