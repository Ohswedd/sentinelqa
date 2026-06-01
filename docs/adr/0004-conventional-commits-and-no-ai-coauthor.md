# ADR-0004: Conventional Commits + no-AI-coauthor enforcement

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

our engineering rules§3 forbids listing any AI tool as a Git author, co-author, owner, or maintainer. Neither rule can be left as a guideline: contributors include LLM coding agents whose default behavior is to add `Co-authored-by: Claude/GPT/Copilot/...` trailers unless explicitly stopped, and ad-hoc commit-message styles destroy the auditability we rely on for trust (our product spec principles). We need both rules to be enforced _mechanically_ so the gate is unmissable.

## Decision

- **Commit-message format:** Conventional Commits with the our engineering rules(`feat`, `fix`, `docs`, `test`, `refactor`, `security`, `ci`, `chore`, `perf`, `build`). Type must be lower-case. Scope is encouraged in kebab-case. Header capped at 100 chars; body / footer lines capped at 200 chars.
- **Local enforcement:** `commitlint.config.cjs` declares `@commitlint/config-conventional` plus the whitelist override; `.pre-commit-config.yaml` runs `alessandrojcm/commitlint-pre-commit-hook` at the `commit-msg` stage with `@commitlint/cli` and `@commitlint/config-conventional` pinned as `additional_dependencies` so the JS env is hermetic. `pre-commit install` wires this hook on every clone (chained into `make install-hooks`).
- **CI enforcement (commit format):** `.github/workflows/commitlint.yml` runs the same commitlint config against every commit in the PR range.
- **CI enforcement (no AI co-author):** `.github/workflows/no-ai-coauthor.yml` rejects any PR whose commit messages contain `Co-authored-by:` followed by `Claude`, `GPT`, `Copilot`, `Gemini`, `Codex`, `Anthropic`, `OpenAI`, `Bard`, `Aider`, `Cursor`, or `Devin`. The list grows as new AI tools appear.
- **Local enforcement (no AI co-author):** documented in `docs/dev/branching.md` and `docs/dev/ownership.md`; covered by the CI gate as the backstop. Bypassing commit hooks with `--no-verify` is forbidden by our engineering rules
- **Pre-push gate:** the `make-ci` local hook (pre-push stage) runs the full quality matrix before any branch leaves the laptop, ensuring no commit lands on the remote with a broken gate.

## Consequences

- **Positive:** Commit messages are machine-parseable, which lets generate a changelog automatically without lossy heuristics.
- **Positive:** AI co-author trailers are mechanically impossible to land. Ownership stays unambiguously human.
- **Positive:** A bad commit on a contributor's laptop fails fast — at the commit-msg stage — before any push or PR opens.
- **Negative / trade-off:** The commitlint hook adds a Node-based environment to the pre-commit toolchain (extra ~30s on first install). Acceptable; the hermetic install reuses pnpm's content-addressed cache.
- **Follow-up obligations:** When a new mainstream AI coding assistant launches, add its name to the `no-ai-coauthor.yml` pattern list within the same week. (final hardening) re-checks this list.

## Alternatives considered

- **Husky for hook management.** Rejected: we already standardized on the Python `pre-commit` framework for gitleaks and the file-hygiene hooks. Adding Husky would mean two hook managers, two install steps, and two failure modes. The `alessandrojcm/commitlint-pre-commit-hook` lets us keep one.
- **No commit-message enforcement; rely on PR review.** Rejected: human reviewers miss style drift, and our engineering rules
- **Disallow only `Co-authored-by: Claude*` via PR template checkbox.** Rejected: a checkbox is not enforcement. A grep-based CI gate is.
- **Allow `Co-authored-by:` for AI tools but tag them under a separate label.** Rejected: our engineering rules("No AI co-author trailers — ever, unless the user explicitly types it themselves").

## References

- our engineering rules§4 Git workflow, §17 Quality Gates.
- External: <https://www.conventionalcommits.org/>, <https://commitlint.js.org/>, <https://github.com/alessandrojcm/commitlint-pre-commit-hook>.
- Related ADRs: ADR-0002 (language strategy — explains why a Node-based hook is acceptable in a Python-leaning toolchain).
