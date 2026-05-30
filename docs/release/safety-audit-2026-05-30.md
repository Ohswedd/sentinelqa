---
title: 'SentinelQA — Safety Boundary Audit'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — Safety Boundary Audit (Phase 29.01)

## Scope

Re-audit PRD §2 / CLAUDE.md §6 across every module that performs I/O against a
target, every CLI command that can be aimed at a URL, and the cross-cutting
infrastructure that backs them (config loader, safety policy, forbidden-flag
registry, HTTP clients, JSONL runtime headers).

Per-module verdict criteria (from `plans/phase-29-final-hardening/01-safety-audit.md`):

1. `SafetyPolicy.enforce(...)` is called **before** any network call.
2. No `--stealth` / `--evade` / `--bypass-*` / `--undetectable` flags exist.
3. The User-Agent header is transparent.
4. The `X-SentinelQA-Test-Run` header is sent.
5. Rate limits are applied.
6. An audit log entry is written per significant decision.

## Top-line verdict

**PASS.** Every module that performs target I/O calls `SafetyPolicy.enforce(...)`
before any network is touched, exits 4 (`UnsafeTargetError`) when the target is
out-of-policy, and writes a redacted entry into `.sentinel/runs/<id>/audit.log`.
The forbidden-flag registry is enforced by tests on every CI run. No stealth /
evasion / bypass capability is reachable from the CLI, the SDK, the MCP server,
the plugin loader, or the TS runtime.

A live red-team probe against `https://example.com` (a host not on any
allowlist) was refused with exit code 4 and a structured `E-SAFE-001` error in
both human and JSON modes — see "Red-team probe" below for the full output.

## SafetyPolicy.enforce call sites

```
engine/orchestrator/run_lifecycle.py:260      RunLifecycle.execute() — single canonical enforce hop for `audit`
engine/runner/docker.py:118                   DockerRunner.run() — re-enforces before launching the container
apps/cli/src/sentinel_cli/commands/discover_cmd.py:100
apps/cli/src/sentinel_cli/commands/plan_cmd.py:120
apps/cli/src/sentinel_cli/commands/generate_cmd.py:137
apps/cli/src/sentinel_cli/commands/doctor_cmd.py:224
modules/security/module.py:117                Re-enforced at module entry
modules/security/checks/headers.py:35
modules/security/checks/cookies.py:121
modules/security/checks/cors.py:34
modules/security/checks/csrf.py:69
modules/security/checks/idor.py:94
modules/security/checks/sqli.py:122
modules/security/checks/xss_reflected.py:74
modules/security/checks/xss_stored.py:96
modules/security/checks/frontend_secrets.py:102
modules/api/module.py:115
modules/chaos/module.py:181
```

Every module that does network I/O appears in this list; the four CLI commands
that take `--url` enforce safety in the command handler _before_ the lifecycle
is even constructed, and the lifecycle then re-enforces internally (PRD §10).

Enforcement is unit-tested by `tests/security/test_module_calls_policy.py`
(every concrete module's `module.py` is scanned for a `SafetyPolicy().enforce`
call). It is integration-tested by exit-code tests on every CLI command path
(`tests/integration/cli/test_*_command.py::test_*_unsafe_*`) and by the
discovery/runner integration tests under `tests/integration/runner/` and
`tests/integration/discovery/`.

## Forbidden flags & capabilities

`engine/policy/forbidden_features.py` is the canonical deny list:

- 18 capability strings: `bot_detection_bypass`, `captcha_bypass`,
  `captcha_solving`, `stealth_automation`, `fingerprint_evasion`,
  `fingerprint_spoofing`, `credential_stuffing`, `session_theft`,
  `cookie_theft`, `data_exfiltration`, `spam_automation`,
  `platform_manipulation`, `phishing`, `proxy_rotation_for_evasion`,
  `rate_limit_bypass`, `unauthorized_exploit`, `destructive_against_public`,
  `undetectable_mode`.
- 9 CLI flag strings: `--stealth`, `--evade`, `--evasion`, `--bypass`,
  `--bypass-captcha`, `--bypass-rate-limit`, `--undetectable`,
  `--rotate-proxies`, `--spoof-fingerprint`.

Enforcement is layered:

1. **Static codebase scan** —
   `tests/security/test_no_stealth_flags.py` greps the entire source tree
   for any forbidden capability or flag; CI fails on a hit.
2. **Plugin loader** — `engine/plugins/loader.py` calls
   `assert_capability_allowed(...)` on every capability declared in a plugin
   manifest before any code is imported (ADR-0029, Phase 24).
3. **Per-module guards** — `tests/security/test_api_no_aggressive_flags.py`,
   `tests/security/test_chaos_no_evasion_flags.py`,
   `tests/security/test_security_forbidden_flags.py` enforce that the API,
   chaos, and security modules cannot accept a forbidden flag via their
   `ModuleOptions` dataclass.
4. **MCP surface** — `tests/security/test_mcp_safety.py` asserts none of the
   `sentinel.*` tool schemas expose a forbidden flag as an input parameter.

A live `grep -rE "--stealth|--evade|--bypass" --include='*.py' --include='*.ts'`
across `engine/`, `apps/`, `modules/`, `integrations/`, `packages/` returns
**zero** hits in non-test code (the only hits are in
`engine/policy/forbidden_features.py` and the security tests that read it).

## Transparent User-Agent

| Code path                                         | Hard-coded User-Agent                                                                                                                                                                            |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `engine/discovery/crawler.py`                     | `SentinelQA/<engine version>` (set by `_sentinel_user_agent()`).                                                                                                                                 |
| `engine/discovery/backends/playwright_backend.py` | Same UA, propagated into Playwright's `extraHTTPHeaders`.                                                                                                                                        |
| `modules/security/http_client.py:22`              | `SentinelQA-Security/1.0 (+https://sentinelqa.dev)`.                                                                                                                                             |
| `modules/api/http_client.py:21`                   | `SentinelQA-Api/1.0 (+https://sentinelqa.dev)`.                                                                                                                                                  |
| `integrations/_http.py:28`                        | `sentinelqa-integrations/1`.                                                                                                                                                                     |
| `integrations/github/post_pr_comment.py:39`       | `sentinelqa-pr-poster/1`.                                                                                                                                                                        |
| `integrations/gitlab/post_mr_note.py:38`          | `sentinelqa-mr-poster/1`.                                                                                                                                                                        |
| `packages/ts-runtime/src/cli.ts:373`              | Sets `extraHTTPHeaders` including the run-id header; UA is the standard Playwright UA, which is acceptable for browser automation (PRD §2.2) and is **not** spoofed to mimic a third-party user. |

No code path uses a faked desktop/mobile UA, randomized UA pool, or
`headless=false` UA scrubbing.

## `X-SentinelQA-Test-Run` header

Sent on every outbound HTTP request from:

- `engine/discovery/crawler.py:236` (crawl + robots.txt fetches).
- `engine/discovery/backends/playwright_backend.py:31` (Playwright crawl).
- `modules/security/http_client.py:69` (every security check).
- `modules/api/http_client.py:69` (every API contract probe).
- `packages/ts-runtime/src/cli.ts:373` (Playwright browser sessions).

The header value is the canonical `run_id` (`run_<timestamp>_<hex>`), which
gives the target operator a single grep handle for everything SentinelQA did
during the run.

## Rate limits

- `engine/config/schema.py:355` ships a default
  `target.rate_limit_rps = 5.0` with hard bounds `> 0.0` and `≤ 100.0`.
- `engine/discovery/crawler.py:68` consumes that via a token-bucket
  (`_TokenBucket`) applied to every crawl/probe call (`crawler.py:232`).
- The Playwright backend inherits the same value
  (`engine/discovery/backends/playwright_backend.py:84/99/206`).
- `rate_limit_bypass` is in `FORBIDDEN_CAPABILITIES`; no module can request
  it via plugin manifest or runtime flag.

## Audit log entries

Every significant safety decision is appended (atomic, redacted, JSONL) to
`.sentinel/runs/<id>/audit.log` by `engine/safety/policy.py::SafetyPolicy.enforce`:

- `safety_policy_evaluated` (every call: target host, mode, verdict).
- Module-entry events (`module_started`/`module_finished`) by
  `engine/orchestrator/run_lifecycle.py`.
- Artifact emit events by the reporter dispatcher
  (`artifact_emitted`).
- All entries are routed through `engine/redact/` so credentials, cookies,
  Authorization headers, and tokens are stripped before disk.

Per-CLI-command, the discovery/plan/generate/doctor handlers each call
`SafetyPolicy().enforce(target, audit_log_path=audit_log_path)` so the audit
log is written even when the lifecycle never starts (e.g. unsafe-target
refusal).

## Red-team probe

Probe (2026-05-30, fresh clone of `main` + Phase 29 branch):

```
$ uv run sentinel --ci --json \
    --config examples/nextjs/sentinel.config.yaml \
    discover --url https://example.com
{"code":"E-SAFE-001","context":{"allowed_hosts":["127.0.0.1","localhost"],"host":"example.com","mode":"safe"},"exit_code":4,"message":"Host 'example.com' is not in target.allowed_hosts and is not local.","suggested_fix":"Add the host to `target.allowed_hosts` only if you own or are authorized to test it. SentinelQA never permits unauthorized scans (PRD §2, CLAUDE.md §6).","type":"error"}
```

- Exit code: **4** (`UnsafeTargetError`).
- Stdout payload: single line of structured JSON (no logs, no banner, no
  ANSI sequences — `JSON_MODE` stdout-purity guard active).
- Hint surfaces the PRD/CLAUDE.md anchors so a human operator can verify.
- The audit log under `.sentinel/runs/<id>/audit.log` contains the refusal
  record (asserted by `tests/security/test_safety_policy.py::test_audit_log_records_refusal`).

A second probe with `--mode authorized_destructive` set in config still
refuses the public target — the destructive branch only loosens behavior
_inside_ an allowlisted host; it never expands the allowlist.

## Per-module verdicts

| Module                                                      | enforce() before I/O                                                                                   | Forbidden flags absent                                      | Transparent UA                                                                                               | Run-id header                      | Rate-limit                                  | Audit log entry                           | Verdict |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------- | ------------------------------------------- | ----------------------------------------- | ------- |
| **discovery (HTTP)**                                        | ✅ `discover_cmd.py:100`                                                                               | ✅                                                          | ✅ `SentinelQA/<ver>`                                                                                        | ✅                                 | ✅ token bucket                             | ✅                                        | PASS    |
| **discovery (Playwright)**                                  | ✅ same                                                                                                | ✅                                                          | ✅                                                                                                           | ✅                                 | ✅                                          | ✅                                        | PASS    |
| **planner**                                                 | ✅ `plan_cmd.py:120`                                                                                   | ✅                                                          | ✅ (no direct network; LLM provider is configurable per-tenant, redacted)                                    | n/a (LLM API call, not target I/O) | n/a                                         | ✅                                        | PASS    |
| **generator**                                               | ✅ `generate_cmd.py:137`                                                                               | ✅                                                          | n/a (no target I/O)                                                                                          | n/a                                | n/a                                         | ✅                                        | PASS    |
| **runner (local)**                                          | ✅ via lifecycle                                                                                       | ✅                                                          | inherits Playwright UA + run-id header                                                                       | ✅                                 | n/a (test-driver path)                      | ✅                                        | PASS    |
| **runner (Docker)**                                         | ✅ `engine/runner/docker.py:118` (re-enforces in-container)                                            | ✅ no `--privileged`, no socket mount                       | inherits Playwright UA                                                                                       | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **analyzer**                                                | n/a (no target I/O)                                                                                    | ✅                                                          | n/a                                                                                                          | n/a                                | n/a                                         | n/a (post-run analysis)                   | PASS    |
| **functional**                                              | ✅ via runner                                                                                          | ✅                                                          | ✅                                                                                                           | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **accessibility**                                           | ✅ via lifecycle + `modules/accessibility/runner.py`                                                   | ✅                                                          | inherits Playwright UA                                                                                       | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **performance**                                             | ✅ via lifecycle + `modules/performance/runner.py`                                                     | ✅ synthetic-labeling test                                  | inherits Playwright UA                                                                                       | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **security (safe)**                                         | ✅ `modules/security/module.py:117` + per-check re-enforce                                             | ✅ `test_security_forbidden_flags.py`                       | ✅ `SentinelQA-Security/1.0`                                                                                 | ✅                                 | inherits target.rate_limit_rps              | ✅                                        | PASS    |
| **quality_scoring**                                         | n/a (no I/O)                                                                                           | ✅                                                          | n/a                                                                                                          | n/a                                | n/a                                         | ✅ via reporter                           | PASS    |
| **html/json reports**                                       | n/a (writes to local disk only)                                                                        | ✅                                                          | n/a                                                                                                          | n/a                                | n/a                                         | ✅ `artifact_emitted`                     | PASS    |
| **api**                                                     | ✅ `modules/api/module.py:115`                                                                         | ✅ `test_api_no_aggressive_flags.py`                        | ✅ `SentinelQA-Api/1.0`                                                                                      | ✅                                 | inherits target.rate_limit_rps              | ✅                                        | PASS    |
| **chaos**                                                   | ✅ `modules/chaos/module.py:181`                                                                       | ✅ `test_chaos_no_evasion_flags.py`                         | inherits Playwright UA (chaos = network shaping at the page level, not arbitrary network I/O against extras) | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **visual**                                                  | ✅ via lifecycle                                                                                       | ✅                                                          | inherits Playwright UA                                                                                       | ✅                                 | n/a                                         | ✅                                        | PASS    |
| **llm_audit**                                               | ✅ via lifecycle                                                                                       | ✅                                                          | inherits crawler UA                                                                                          | ✅                                 | inherits target.rate_limit_rps              | ✅                                        | PASS    |
| **healer**                                                  | n/a (operates on stored traces; no target I/O)                                                         | ✅ confidence-gated suggestions, no auto-merge              | n/a                                                                                                          | n/a                                | n/a                                         | ✅                                        | PASS    |
| **mcp server**                                              | ✅ every tool call enforces SafetyPolicy via the lifecycle                                             | ✅ `tests/security/test_mcp_safety.py`                      | inherits caller UA                                                                                           | n/a (server, not client)           | n/a                                         | ✅                                        | PASS    |
| **plugin loader**                                           | n/a (loads code; safety boundary is the capability deny-list)                                          | ✅ `assert_capability_allowed` on every declared capability | n/a                                                                                                          | n/a                                | n/a                                         | ✅ rejection logged                       | PASS    |
| **integrations (Slack/Linear/Jira/BrowserStack/SauceLabs)** | n/a (do **not** call target — they call third-party APIs on the user's behalf, with documented opt-in) | ✅ no evasion flags                                         | ✅ `sentinelqa-integrations/1` (sub-branded per integration)                                                 | n/a (not a target probe)           | ✅ each adapter has per-call retry/back-off | ✅ via `integrations/_http.py:_audit_log` | PASS    |

## Findings

None blocking. Two informational notes carried in this report (not deferred
scope — they describe the **current** posture and the explicit decision to
keep it):

1. **Planner LLM call is HTTP-only, redacted, capped.** The planner's
   optional `LlmPlanner` adapter posts to OpenAI / Anthropic via `httpx`
   only (no vendor SDK), redacts the request body before logging, caps
   per-run USD spend, and is **off by default** (`planner.llm.enabled:
false`). This is the documented PRD §6 + ADR-0011 decision; no change
   requested.

2. **Integrations are deliberately outbound-only.** Slack, Linear, Jira,
   GitHub status, GitLab status, BrowserStack, and SauceLabs adapters are
   built to post **from** SentinelQA to a service the operator owns. They
   never accept inbound traffic and never call the target under test. This
   is the documented ADR-0030 boundary; no change requested.

## Conclusion

The safety boundary is enforced consistently, tested by CI, and verified by
live red-team probe. No deferred items. Phase 29.01 closes **PASS**.

— ohswedd, 2026-05-30
