# Contributing to SentinelQA

Thank you for working on SentinelQA. This guide is the cold-start: read it
once, then the topic-specific docs under [`docs/`](./docs) for the deep
details.

## Ground rules

- **Safety first.** SentinelQA is for authorized testing only — no stealth,
  no evasion, no unauthorized targets. Every PR is reviewed against the
  safety boundary in [`SECURITY.md`](./SECURITY.md). This is non-negotiable
  in our engineering rules.
- **AI tools may write code, but never as authors.** Do not add
  `Co-authored-by:` trailers for AI tools and do not list AI tools as Git
  authors, owners, or maintainers. The CI `no-ai-coauthor` workflow
  enforces this on every PR.
- **Be kind.** This project follows the [Contributor Covenant Code of
  Conduct](./.github/CODE_OF_CONDUCT.md).

## Quick start for contributors

```bash
# Clone + install
git clone https://github.com/Ohswedd/sentinelqa.git
cd sentinelqa
make install

# Hack on a branch
git checkout -b feature/<short-slug>

# Run the full local gate before pushing
make ci
```

`make install` provisions Python via `uv`, Node + pnpm, and the
`pre-commit` hooks. `make ci` runs format-check, lint, typecheck, ADR
template check, pytest, Prettier, ESLint, `tsc --noEmit`, and Vitest.

## Project layout

```
apps/cli/ Typer CLI (sentinelqa-cli)
apps/docs/ Astro Starlight docs site
engine/ Domain models, orchestrator, scoring, reporter
modules/ Concrete audit modules (functional, a11y, perf,...)
integrations/ BrowserStack, Sauce Labs, Slack, GitHub, GitLab,...
packages/python-sdk/ Public Python SDK (sentinelqa)
packages/mcp-server/ MCP server exposing the sentinel.* tools
packages/ts-runtime/ Playwright runtime and JSONL bridge
scripts/ Build / docs-gen / release scripts
docs/ Long-form developer + user docs, ADRs
tests/ unit + integration + property + security tests
```

## Branching and commits

Use one of the standard prefixes:

```
feature/<name> fix/<name> docs/<name>
refactor/<name> security/<name> ci/<name>
chore/<name>
```

**Conventional Commits are required.** `commitlint` runs in the
`commit-msg` hook locally and in CI. Examples:

```
feat(security): add JWT weakness check
fix(runner): retry flaky Playwright launches up to twice
docs(sdk): document async_audit return type
ci(release): wire the v* tag publish workflow to OIDC
```

The pre-push hook runs `make ci`. Bypassing with `--no-verify` is only
acceptable for a documented emergency.

## Definition of Done

Before opening a PR:

1. Implementation matches the documented behavior (CLI, SDK, MCP).
2. Tests exist and pass (unit + integration as relevant; bug fixes get a
   regression test).
3. Format / lint / typecheck are clean (`make ci`).
4. Safety implications reviewed against [`SECURITY.md`](./SECURITY.md).
5. Reports / schemas updated if you changed an output format.
6. Docs updated if behavior changed.
7. No secrets or generated junk staged (`git status` clean after commit).

## Tests

No feature is complete without tests. The required categories vary by area:

- **Unit** — pure logic in `tests/unit/`.
- **Integration** — multi-module flows in `tests/integration/`.
- **CLI smoke** — when CLI surface changes.
- **Schema / golden** — when persisted artifacts change (`make update-goldens`
  regenerates with explicit confirmation; never commit unintended golden
  drift).
- **Security policy** — when target handling, allowlists, or check logic
  changes.
- **Report / SARIF** — when report shapes change.

Run a targeted subset with `uv run pytest tests/unit/modules/security/ -v`
or the full suite with `make ci`. Slow and property-based tests are
excluded from `make ci`; run them with `make test-full`.

## Architecture Decision Records (ADRs)

If your change touches runtime architecture, plugin contracts, config
schema, scoring, report schemas, security policy, the agent / MCP design,
or the cloud boundary — write an ADR in [`docs/adr/`](./docs/adr/) before
the implementation lands. Use [`docs/adr/_template.md`](./docs/adr/_template.md)
as the starting point.

## Security and secrets

- Never commit `.env`, credentials, tokens, traces containing secrets, or
  real customer data. Provide `.env.example` only.
- Secret-shaped strings in test fixtures must be allowlisted in
  [`.gitleaks.toml`](./.gitleaks.toml) with a comment naming the test.
- Vulnerabilities go through the disclosure path in
  [`SECURITY.md`](./SECURITY.md), not public issues.

## Releasing

Release engineering lives in [`docs/release/publish-runbook.md`](./docs/release/publish-runbook.md)
and the four `.github/workflows/publish-*.yml` workflows. Tagging and
publishing are maintainer actions, never delegated to automation.

## Getting unstuck

- Re-read the relevant section of [`docs/`](./docs/) — the rule is almost
  always there.
- Check the [Architecture Decision Records](./docs/adr/) for the rationale
  behind a contested design choice.
- Open a draft PR with the failing run output; reviewers can usually see
  the issue in the first read.

Thanks for contributing.
