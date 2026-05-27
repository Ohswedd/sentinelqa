# CLAUDE.md

# SentinelQA Engineering Constitution

This file is the mandatory operating manual for AI coding agents and human contributors working on **SentinelQA**.

It does **not** replace the PRD. The PRD defines product scope. This file defines how the project must be built.

---

## 1. Prime Directive

SentinelQA must be built as a production-grade, Playwright-native release-confidence engine for LLM-built and human-built software.

Every change must optimize for:

1. Correctness
2. Safety
3. Determinism
4. Maintainability
5. Testability
6. Security
7. Extensibility
8. Developer experience
9. Auditability
10. PRD alignment

Never fake completeness. Never weaken tests to make them pass. Never ship behavior that contradicts the PRD.

---

## 2. Authority Order

When instructions conflict, follow this order:

1. System/developer safety rules
2. User instructions
3. `CLAUDE.md`
4. `PRD.md`
5. ADRs
6. Inline code comments

If `CLAUDE.md` and the PRD conflict, stop, resolve the conflict explicitly, update the PRD or this file, and commit the correction.

---

## 3. Repository Privacy and Ownership

The repository must stay private until the owner explicitly decides otherwise.

Do not:

- Make the repo public
- Add AI tools, editors, models, or vendors as owners/co-owners
- Add AI tools as package maintainers
- Add `Co-authored-by:` trailers for AI tools unless explicitly requested
- Add legal authorship, copyright, or ownership references to AI tools
- Configure the editor, agent, or model as a project owner

Git authorship must remain under the human owner or an explicitly configured human identity.

---

## 4. Required Git Workflow

Never work directly on `main` unless explicitly instructed.

Use branches:

```bash
feature/<name>
fix/<name>
docs/<name>
refactor/<name>
security/<name>
ci/<name>
```

Commit after each coherent unit of work.

Use Conventional Commits:

```text
feat(scope): summary
fix(scope): summary
docs(scope): summary
test(scope): summary
refactor(scope): summary
security(scope): summary
ci(scope): summary
chore(scope): summary
```

Before committing:

1. Inspect `git status`
2. Run relevant tests/checks that exist
3. Update docs/PRD if behavior changed
4. Ensure no secrets or generated junk are staged
5. Commit with a precise message

Never claim work is complete if there are uncommitted relevant changes.

---

## 5. PRD Discipline

The PRD is the product source of truth.

Update `PRD.md` in the same branch when any of these change:

- Product behavior
- CLI contract
- SDK contract
- Module lifecycle
- Safety boundary
- Report schema
- Data model
- Quality scoring
- Roadmap
- Competitive positioning
- Implementation reveals the PRD is wrong or incomplete

Do not silently diverge from the PRD.

If a defect, limitation, or architectural risk is found, document it in the PRD or ADRs before moving on.

---

## 6. Non-Negotiable Safety Boundary

SentinelQA is for authorized testing only.

Forbidden features:

- Bot-detection bypass
- CAPTCHA bypass
- Stealth automation to hide from third-party systems
- Fingerprint evasion
- Credential stuffing
- Spam automation
- Platform manipulation
- Unauthorized vulnerability exploitation
- Proxy rotation for evasion
- Rate-limit bypass
- Destructive testing against public targets
- Cookie/session theft
- Data exfiltration
- Phishing flows
- Malware-like behavior

Allowed direction:

- Authorized security assessment
- Safe adversarial testing
- Compliant realism
- Transparent browser automation
- Audit logs
- Rate limits
- Target allowlists
- Proof-of-authorization gates

Never market or implement SentinelQA as “undetectable.”

---

## 7. Architecture Rules

Use layered architecture:

```text
CLI / SDK / Agent Interface
        ↓
Application Services
        ↓
Domain Core
        ↓
Ports / Protocols
        ↓
Adapters / Integrations
        ↓
External Tools
```

Core domain must not depend directly on Typer, Click, FastAPI, Playwright, GitHub Actions, BrowserStack, cloud APIs, or LLM vendors.

External tools belong behind adapters.

Use dependency inversion. Core depends on interfaces, not implementations.

Keep modules small, cohesive, and replaceable.

---

## 8. Runtime Ownership

Python owns:

- CLI
- SDK
- Orchestration
- Config
- Policy enforcement
- Module registry
- Scoring
- Reports
- Agent-facing operations
- CI behavior

TypeScript owns:

- Playwright execution
- Browser automation
- Locator utilities
- Runtime tracing
- Screenshot/video/trace capture
- Browser-side instrumentation

Python ↔ TypeScript communication must be explicit and structured, preferably JSON/JSONL for MVP.

Do not create hidden coupling between runtimes.

---

## 9. Module Contract

Every capability must behave like a module/plugin.

Each module must expose the same conceptual lifecycle:

```text
validate prerequisites
plan checks
execute checks
collect evidence
emit findings
emit metrics
summarize result
```

Modules must not directly control global run lifecycle.

A module failure should produce a typed partial result unless the failure invalidates the entire run.

---

## 10. Run Lifecycle

Every audit run must follow this lifecycle:

```text
load config
validate config
resolve target
enforce safety policy
create run id
create artifact directory
snapshot config
discover app
build execution plan
run modules
collect evidence
normalize findings
calculate quality score
apply quality gates
generate reports
persist artifacts
return deterministic exit code
```

Never skip safety policy.

Never emit a successful report for an incomplete run without marking it incomplete.

---

## 11. Artifact and Data Rules

Each run must be isolated:

```text
.sentinel/runs/<run-id>/
```

Persist, when available:

```text
run.json
config.snapshot.yaml
findings.json
score.json
report.html
report.md
junit.xml
sarif.json
traces/
screenshots/
videos/
logs/
```

Machine-readable files must include schema versions.

Scores must be reproducible from stored findings and metrics.

---

## 12. Config Rules

Configuration must be validated strictly.

Rules:

- Safe defaults
- Explicit errors for invalid config
- No silent dangerous fallback
- Environment interpolation allowed
- Secrets redacted everywhere
- Unknown risky keys rejected
- CI-safe behavior without prompts

Security/adversarial modules must require explicit target authorization.

---

## 13. CLI Rules

CLI must be predictable and scriptable.

Every command must support useful help.

Where relevant, support:

```bash
--config
--json
--verbose
--quiet
--ci
--url
--output
--fail-under
--dry-run
```

JSON mode must output only machine-readable JSON, no logs or ANSI formatting.

Deterministic exit codes are mandatory.

Suggested exit codes:

```text
0 success
1 quality gate failed
2 invalid config
3 runtime error
4 unsafe target blocked
5 dependency missing
6 test execution failed
7 internal error
```

---

## 14. SDK Rules

The Python SDK must be first-class, typed, and stable.

Public APIs must use explicit models and return structured results.

Do not expose internal implementation details through package root imports.

Any documented SDK behavior is public contract and requires tests.

---

## 15. Agent Interface Rules

SentinelQA must be usable by LLM coding agents through explicit operations.

Agent-facing operations must be:

- Deterministic where possible
- Structured
- Evidence-based
- Safe by default
- Stateless or explicit about state
- Parseable by machines

Required conceptual operations:

```text
discover_app
generate_test_plan
generate_tests
run_audit
read_failures
summarize_findings
suggest_test_fix
verify_fix
update_prd
```

Do not bury critical product logic inside unversioned prompts.

---

## 16. Testing Standard

No feature is complete without tests.

Required where relevant:

- Unit tests
- Integration tests
- CLI tests
- Schema/golden tests
- Security policy tests
- Report tests
- Playwright runtime tests
- Regression tests for bugs

Bug fixes require regression tests unless impossible. If impossible, document why.

Never weaken or delete meaningful tests to pass CI.

---

## 17. Quality Gates

Before marking a task done:

1. Format
2. Lint
3. Typecheck
4. Unit tests
5. Relevant integration tests
6. CLI smoke test when CLI changed
7. Security policy tests when target/scanning behavior changed
8. Report/schema tests when output changed
9. Docs/PRD update if needed
10. Commit

Only run commands that exist. If essential commands are missing, add them deliberately and document them.

---

## 18. Definition of Done

A task is done only when:

- Implementation matches PRD
- Tests exist and pass
- Types/lint pass where configured
- Safety implications are reviewed
- Reports/schemas are updated if affected
- Docs/PRD are updated if behavior changed
- No secrets are introduced
- Git status is clean after commit

---

## 19. Code Quality Rules

Use SOLID design without overengineering.

Prefer:

- Small cohesive modules
- Typed public APIs
- Pure domain logic where possible
- Explicit errors
- Stable schemas
- Dependency injection
- Adapter boundaries
- Deterministic outputs

Avoid:

- Global mutable state
- Hidden network calls
- Broad silent exception handling
- Business logic in CLI handlers
- Hardcoded fake results
- God objects
- Circular dependencies
- Framework leakage into domain core

---

## 20. Python Rules

Use modern typed Python.

Required style:

- Type hints for public functions
- `pathlib` for paths
- `pytest` for tests
- `ruff` when configured
- `mypy` or equivalent when configured
- Pydantic/dataclasses for structured models
- Explicit custom exceptions for expected failures

Do not place core business logic in command handlers.

---

## 21. TypeScript / Playwright Rules

Use strict TypeScript.

For Playwright tests and generated specs, prefer semantic locators:

```ts
page.getByRole("button", { name: /submit/i })
page.getByLabel("Email")
page.getByText("Dashboard")
```

Avoid brittle selectors unless no semantic option exists.

Do not use arbitrary sleeps. Prefer Playwright auto-waiting and assertions.

Collect trace/screenshot/video evidence on failures when configured.

---

## 22. Generated Test Rules

Generated tests must be:

- Readable
- Deterministic
- Maintainable
- Minimal but meaningful
- CI-compatible
- Based on user flows
- Based on semantic locators where possible
- Explicit about confidence when generated from heuristics

Never generate tests that only assert the page loaded unless that is the intended smoke test.

---

## 23. Self-Healing Rules

Self-healing must be conservative.

Allowed:

- Locator repair with high confidence
- Suggested patches for medium confidence
- Human review for risky changes

Forbidden:

- Weakening assertions to force green tests
- Changing test intent silently
- Hiding app bugs as test repairs
- Auto-accepting uncertain fixes

Every repair proposal must include:

```text
original behavior
proposed change
confidence
reason
evidence
review requirement
```

---

## 24. Findings Rules

Findings must be specific and evidence-backed.

Every finding needs:

```text
id
run id
module
category
severity
confidence
title
description
evidence
recommendation
affected target
created timestamp
```

Do not emit vague findings.

Bad:

```text
Security issue found.
```

Good:

```text
Session cookie on /login is missing HttpOnly and Secure flags.
```

---

## 25. Quality Score Rules

Quality score must be explainable and reproducible.

It must derive from:

- Findings
- Severity
- Confidence
- Module weights
- Coverage
- Flake risk
- Blocking issues
- Configured gates

Blockers must fail CI.

Critical findings should fail CI by default unless configured otherwise.

Never hardcode fake scores.

---

## 26. Security Module Rules

Security checks are safe by default.

Default allowed targets:

```text
localhost
127.0.0.1
::1
explicitly configured staging hosts
```

Public targets must be blocked unless explicitly allowlisted.

Security findings must include risk, evidence, and safe remediation.

Do not include exploit weaponization.

---

## 27. Performance Module Rules

Performance checks must be budget-based and labeled as synthetic.

Use repeated or median measurements where practical.

Do not overstate lab results as real-user monitoring.

Persist relevant metrics and evidence.

---

## 28. Accessibility Module Rules

Automated accessibility checks must not claim full WCAG compliance.

Correct language:

```text
Automated accessibility checks passed.
```

Incorrect language:

```text
This app is fully WCAG compliant.
```

---

## 29. Visual Regression Rules

Visual baselines must not be auto-accepted in CI unless explicitly configured.

Visual diffs must store artifacts and thresholds.

Visual findings must distinguish intentional change from likely regression when possible, but must not guess without evidence.

---

## 30. API Testing Rules

API tests should support schemas, contracts, negative cases, auth, and latency budgets.

Do not run aggressive fuzzing against untrusted or unauthorized targets.

---

## 31. LLM-Code Audit Rules

Prioritize detection of AI-generated app failure modes:

- Dead buttons
- Fake flows
- Missing endpoints
- Mock data shipped
- Frontend-only auth
- Missing server validation
- Broken generated clients
- Incomplete CRUD
- Placeholder/TODO leakage
- Error/loading state gaps
- Admin UI without authorization checks

These checks are a core differentiator and must remain visible in design decisions.

---

## 32. Error Handling

Expected errors must be typed and actionable.

Each should include:

- Error code
- Human-readable message
- Technical context
- Suggested fix
- Redacted details

Do not swallow exceptions silently.

Verbose stack traces are for debug mode, not default UX.

---

## 33. Logging and Secrets

Never log secrets.

Redact:

- Passwords
- Tokens
- Cookies
- Authorization headers
- Session IDs
- API keys
- Private keys

Never commit `.env`, credentials, tokens, traces containing secrets, or real customer data.

Provide `.env.example` only.

---

## 34. Documentation Rules

Keep docs accurate and status-labeled.

Use:

```text
Planned
Experimental
Stable
Deprecated
```

Do not document non-existing features as available.

Create ADRs for major architectural choices.

Required ADR triggers:

- Runtime architecture
- Plugin system
- Config schema
- Scoring algorithm
- Report schema
- Security policy
- Agent/MCP design
- Cloud boundary

---

## 35. Dependency Rules

Add dependencies only when they are necessary, maintained, secure, license-compatible, and worth their complexity.

Prefer boring, stable tools.

Do not add large frameworks for small utilities.

External tools must be wrapped behind adapters.

---

## 36. Refactoring Rules

Refactor only to improve clarity, safety, testability, maintainability, or extensibility.

Do not mix large refactors with unrelated features.

For risky refactors:

1. Add/confirm tests first
2. Refactor
3. Prove behavior is preserved
4. Commit separately

---

## 37. No Placeholder Completion

Forbidden unless explicitly marked and tracked:

```text
fake success
fake scanner
fake report
hardcoded score
return {}
return True
pass
TODO without issue/PRD note
```

Interfaces may use `NotImplementedError` when concrete adapters are expected.

---

## 38. Report Rules

Reports must serve developers, QA, security reviewers, managers, and agents.

A useful report answers:

```text
What happened?
Where?
How severe?
How confident?
What evidence exists?
Why does it matter?
How should it be fixed?
Does it block release?
```

Machine-readable reports must be schema-stable and versioned.

---

## 39. CI Rules

CI must be non-interactive and deterministic.

CI mode must:

- Use configured quality gates
- Save artifacts
- Return correct exit code
- Avoid prompts
- Avoid local-only assumptions
- Not auto-accept baselines

---

## 40. Versioning and Release Rules

Use semantic versioning.

Before `1.0.0`, breaking changes are allowed but must be documented.

Do not publish packages without explicit approval.

Before any release:

- Tests pass
- Changelog updated
- Version bumped
- Docs updated
- Security boundary reviewed
- Package contents inspected

---

## 41. Privacy and Telemetry

No telemetry by default.

If telemetry is ever added, it must be opt-in, documented, redacted, and disableable.

Never upload source code, reports, traces, screenshots, or secrets without explicit user consent.

---

## 42. Competitor Awareness

Do not copy competitor code, docs, branding, or proprietary workflows.

SentinelQA must differentiate through:

- Playwright-native execution
- Open-core developer workflow
- First-class Python SDK
- LLM-agent integration
- Release-confidence scoring
- Safety-first security checks
- LLM-code-specific audits

If a feature does not strengthen this position, deprioritize it.

---

## 43. Implementation Order

Prefer this order unless the PRD says otherwise:

```text
repo structure
config schema
core domain models
CLI skeleton
run lifecycle
report schemas
Playwright adapter
discovery module
functional module
accessibility module
safe security module
performance module
quality scoring
HTML/JSON reports
Python SDK
CI integration
agent interface
self-healing
visual regression
```

Do not start with cloud/dashboard/marketplace/distributed execution before the core engine is reliable.

---

## 44. Required Review Before Completion

Before final response or handoff, verify:

```text
PRD aligned?
Safety preserved?
Tests added?
Checks passed?
Docs updated?
Schemas updated?
No secrets?
No fake completion?
Committed cleanly?
```

If any answer is no, continue or clearly report the remaining gap.

---

## 45. Final Rule

SentinelQA must earn trust through evidence.

Every feature should make the product more capable of answering one question:

```text
Can this software be trusted enough to ship?
```

If a change does not help answer that question safely and accurately, do not build it.
