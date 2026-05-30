---
title: 'SentinelQA — CLAUDE.md Coverage Matrix'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — CLAUDE.md Coverage Matrix (Phase 29.07)

This matrix walks every §1–§45 section of `CLAUDE.md` and records the
**enforcement mechanism** for each rule. Where a rule is only documented
(no automated check yet), the column lists the manual review checklist
that owns it. The aim is that every high-risk rule is gated by something
that runs in CI; everything else has a named owner.

|   § | Title                             | Enforcement                                                                                                                                                                                                                                                       |
| --: | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1 | Prime Directive                   | Cross-cutting; verified by the phase-gate review row in `STATUS.md` (signed per phase).                                                                                                                                                                           |
|   2 | Authority Order                   | Documented in `CLAUDE.md`. Conflict resolution is recorded in the PRD/CLAUDE sync log in `STATUS.md`.                                                                                                                                                             |
|   3 | Repository Privacy and Ownership  | Enforced by `.pre-commit-config.yaml` `commitlint` + `tests/security/test_commit_messages.py` (banned co-author trailers); `gitleaks` keeps secret-bearing identity files out.                                                                                    |
|   4 | Required Git Workflow             | Enforced by branch-name + Conventional Commits in `commitlint.config.cjs` + `make ci`.                                                                                                                                                                            |
|   5 | PRD Discipline                    | Enforced by the **PRD / CLAUDE.md sync log** row required at every phase gate in `STATUS.md`.                                                                                                                                                                     |
|   6 | Non-Negotiable Safety Boundary    | Enforced by `tests/security/*` (incl. `test_no_stealth_flags.py`, `test_module_calls_policy.py`, `test_mcp_safety.py`, `test_security_forbidden_flags.py`, `test_api_no_aggressive_flags.py`, `test_chaos_no_evasion_flags.py`) + the Phase 29.01 red-team probe. |
|   7 | Architecture Rules                | Enforced by `mypy --strict` (no framework leakage into `engine/domain`), package boundaries (`engine.domain` cannot import `typer`/`fastapi`/`playwright`), and ADR-0001.                                                                                         |
|   8 | Runtime Ownership                 | Enforced by Python ↔ TS JSONL bridge tests (`tests/integration/runner/`) + ADR-0034.                                                                                                                                                                             |
|   9 | Module Contract                   | Enforced by `engine.modules.base.SentinelModule` (ADR-0015) + `tests/unit/modules/test_module_contract.py`.                                                                                                                                                       |
|  10 | Run Lifecycle                     | Enforced by `tests/integration/cli/test_run_lifecycle.py` (every step in the canonical 17-step lifecycle is exercised).                                                                                                                                           |
|  11 | Artifact and Data Rules           | Enforced by `tests/integration/reporter/test_schemas_are_valid.py` + `engine/orchestrator/artifacts.py` (atomic writes; latest pointer).                                                                                                                          |
|  12 | Config Rules                      | Enforced by `engine/config/loader.py` strict validation (unknown-key rejection, inline-secret refusal) + `tests/unit/config/`.                                                                                                                                    |
|  13 | CLI Rules                         | Enforced by `tests/integration/cli/` (every command has --json, --ci, exit-code grid, --help integration tests).                                                                                                                                                  |
|  14 | SDK Rules                         | Enforced by `packages/python-sdk/api-snapshot.json` + `make sdk-api-snapshot` drift gate; deprecation policy in `docs/dev/sdk-deprecation-policy.md`.                                                                                                             |
|  15 | Agent Interface Rules             | Enforced by Phase 18 MCP schema (`packages/shared-schema/agent-envelope.schema.json`) + `tests/integration/mcp/`.                                                                                                                                                 |
|  16 | Testing Standard                  | Enforced by `make ci` + per-phase coverage gates in each phase README (typically ≥ 90% per-package, ≥ 95% overall).                                                                                                                                               |
|  17 | Quality Gates                     | Enforced by `make ci` (format-check + lint + typecheck + adr-check + test).                                                                                                                                                                                       |
|  18 | Definition of Done                | **NEW in Phase 29**: enforced by `make dod` which wraps `make ci` + secret-leak audit + determinism audit + `git status` cleanliness.                                                                                                                             |
|  19 | Code Quality Rules                | Enforced by `ruff` + `mypy --strict` + the architectural boundary tests (§7).                                                                                                                                                                                     |
|  20 | Python Rules                      | Enforced by `ruff` (pyflakes, isort, pyupgrade) + `mypy --strict` + the modern-typing rules in `pyproject.toml`.                                                                                                                                                  |
|  21 | TypeScript / Playwright Rules     | Enforced by `eslint.config.js` + `tsc --noEmit` + the locator-audit subcommand (`sentinel-ts audit-locators`).                                                                                                                                                    |
|  22 | Generated Test Rules              | Enforced by `tests/integration/generator/test_locator_audit.py` + 15 byte-locked template goldens.                                                                                                                                                                |
|  23 | Self-Healing Rules                | Enforced by `tests/unit/healer/` (confidence-gated; risky changes require human review; hard two-retry cap).                                                                                                                                                      |
|  24 | Findings Rules                    | Enforced by `engine/reporter/findings_linter.py` (codes L-FND-001..004 + evidence-required at medium+).                                                                                                                                                           |
|  25 | Quality Score Rules               | Enforced by `engine/scoring/` deterministic computation + `tests/unit/scoring/` reproducibility tests.                                                                                                                                                            |
|  26 | Security Module Rules             | Enforced by `modules/security/` allowlist enforcement + `tests/security/test_security_forbidden_flags.py` + Phase 29.01 red-team.                                                                                                                                 |
|  27 | Performance Module Rules          | Enforced by `tests/security/test_synthetic_perf_labeling.py` (every product output of the perf module must read "synthetic").                                                                                                                                     |
|  28 | Accessibility Module Rules        | Enforced by `tests/security/test_no_wcag_compliance_claims.py` (scans `modules/accessibility/` + `packages/ts-runtime/src/a11y/` on every CI run).                                                                                                                |
|  29 | Visual Regression Rules           | Enforced by `modules/visual/` + `tests/unit/visual/test_no_auto_accept_in_ci.py` + ADR-0026.                                                                                                                                                                      |
|  30 | API Testing Rules                 | Enforced by `tests/security/test_api_no_aggressive_flags.py`.                                                                                                                                                                                                     |
|  31 | LLM-Code Audit Rules              | Enforced by `modules/llm_audit/` test set + the `llm-broken` example (`examples/llm-broken/`) that exercises ≥ 8 anti-patterns.                                                                                                                                   |
|  32 | Error Handling                    | Enforced by `engine/errors/codes.py` `ERROR_REGISTRY` + every typed exception's `to_agent_message()` test.                                                                                                                                                        |
|  33 | Logging and Secrets               | Enforced by `engine/policy/redaction.py` + `engine/log/redaction_filter.py` + `gitleaks` pre-commit + Phase 29.02 secret-leak audit.                                                                                                                              |
|  34 | Documentation Rules               | Enforced by `make docs-check-fresh` (auto-generated pages re-derive cleanly) + ADR template gate (`scripts/check-adrs.sh`).                                                                                                                                       |
|  35 | Dependency Rules                  | Enforced by manual code review at the PR gate (PRD/CLAUDE sync log row). Lockfiles (`uv.lock`, `pnpm-lock.yaml`) prevent unauthorized adds.                                                                                                                       |
|  36 | Refactoring Rules                 | Manual review checklist at the PR gate. Phase-gate review row captures the rationale.                                                                                                                                                                             |
|  37 | No Placeholder Completion         | Enforced by the **Deferred-scope register** in `STATUS.md` (must be empty at every phase gate).                                                                                                                                                                   |
|  38 | Report Rules                      | Enforced by Phase 03 golden tests + `engine/reporter/findings_linter.py` (no vague findings) + Phase 15 HTML/PR/Slack goldens.                                                                                                                                    |
|  39 | CI Rules                          | Enforced by `make ci` non-interactivity + `--ci` flag on every command + `SENTINELQA_ASSERT_JSON_STDOUT=1` runtime guard.                                                                                                                                         |
|  40 | Versioning and Release Rules      | Enforced by `scripts/release/audit_metadata.py` (`make audit-metadata`) + `scripts/release/inspect_built_packages.py` (`make inspect-all`) + `docs/dev/semver.md` (Phase 28).                                                                                     |
|  41 | Privacy and Telemetry             | Documented in `docs/dev/privacy.md` — telemetry is intentionally not implemented. No code path uploads source / reports / traces / screenshots / secrets.                                                                                                         |
|  42 | Competitor Awareness              | Manual review checklist. `docs/dev/competitive-landscape.md` (Phase 27) documents the boundary; no competitor code or branding is imported.                                                                                                                       |
|  43 | Implementation Order              | Enforced by `plans/README.md` phase ordering + `STATUS.md` active-pointer rule (cannot advance past an unfinished phase).                                                                                                                                         |
|  44 | Required Review Before Completion | **NEW in Phase 29**: enforced by `make dod` (mirrors the §44 checklist) + the Phase Gate Review row in `STATUS.md`.                                                                                                                                               |
|  45 | Final Rule                        | Enforced by the Phase 29 audit set itself (this matrix + the safety / secret-leak / determinism / perf / a11y audits) — every audit answers "can this software be trusted enough to ship?" with committed evidence.                                               |

## Rules with only manual enforcement today

These six rules are documented + manually reviewed at the PR / phase-gate
boundary; we deliberately did not introduce automation for them in Phase 29
because the failure modes are subjective (a refactor, a competitor's
phrasing, a "necessary" dependency) and an automated linter would
generate noise without catching the real problems:

- §2 Authority Order
- §35 Dependency Rules
- §36 Refactoring Rules
- §41 Privacy and Telemetry (no telemetry exists, so there is nothing to lint)
- §42 Competitor Awareness
- §43 Implementation Order (the `STATUS.md` active-pointer rule already
  catches phase-order violations; the manual layer is for sub-task
  ordering inside a phase)

Each is owned by the phase-gate reviewer (the human owner per
`CODEOWNERS`) and is captured in the **PR & merge log** in `STATUS.md`.

## What changed in Phase 29 to close §18 and §44

Before this phase, the Definition-of-Done (§18) and the
required-review-before-completion (§44) lists were prose-only. They are
now backed by the `make dod` target which runs:

1. `make ci` (format-check + lint + typecheck + adr-check + test).
2. `tests/integration/release/test_secret_leak.py` (Phase 29.02).
3. `tests/integration/release/test_determinism.py` (Phase 29.03).
4. `git status --porcelain` (must be empty).

So a contributor can run one command locally and get the same verdict the
phase-gate reviewer will give them.

## Conclusion

Every CLAUDE.md rule has a recorded enforcement mechanism. High-risk
rules (safety boundary, secret handling, determinism, score
reproducibility, agent interface, generated test conventions, no fake
completion) are gated by tests that run on every CI run. The six manual
rules are owned by the human reviewer at the PR gate, with the rationale
captured in the sync log. Phase 29.07 closes **PASS**.

— ohswedd, 2026-05-30
