---
title: Security & Safety
description: How SentinelQA enforces its safety boundary in code and in tests.
status: Stable
---

SentinelQA's safety story has three layers: a written boundary
(PRD §2, CLAUDE.md §6), enforcement in code (`SafetyPolicy.enforce`
on every URL-bearing surface), and continuous validation in tests
(`tests/security/` AST guards run on every CI pass).

## The boundary

See [Safety boundary](/concepts/safety-boundary/) for the full list
of forbidden capabilities.

## Where the boundary lives in code

| Surface             | Module                                                         |
| ------------------- | -------------------------------------------------------------- |
| Config load         | `engine.policy.safety.SafetyPolicy`                            |
| CLI flag refusal    | Typer parameter validation in each `sentinel <module>` command |
| Module entry points | `SafetyPolicy().enforce(...)` at the top of every check        |
| MCP tools           | `sentinelqa_mcp.tools._safety.enforce_url`                     |
| Plugin discovery    | Manifest permission-grammar validator                          |

## The guard tests

| Test                                               | What it asserts                                                                           |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `tests/security/test_no_stealth_flags.py`          | No stealth/evasion options in CLI                                                         |
| `tests/security/test_module_calls_policy.py`       | Every `run_*` function in `modules/security/` begins with `SafetyPolicy().enforce(...)`   |
| `tests/security/test_security_forbidden_flags.py`  | Reserved flag names not present anywhere                                                  |
| `tests/security/test_synthetic_perf_labeling.py`   | Every perf finding labels itself synthetic                                                |
| `tests/security/test_no_wcag_compliance_claims.py` | Every a11y output starts with "Automated accessibility check"                             |
| `tests/security/test_api_no_aggressive_flags.py`   | No `--aggressive` / `--fuzz` / `--brute` / `--stress` / `--unbounded` / `--no-rate-limit` |
| `tests/security/test_chaos_no_evasion_flags.py`    | Same family of guards for `sentinel chaos`                                                |
| `tests/security/test_mcp_safety.py`                | Every URL-bearing MCP tool runs `SafetyPolicy.enforce` before any SDK call                |

Each runs on every CI pass. A regression turns the build red.

## Telemetry, privacy, secrets

- **No telemetry** by default (CLAUDE.md §41). If we ever add it,
  it will be opt-in, documented, redacted, and disableable.
- **Secret redaction** applies to every log line, every report,
  every audit-log entry. Passwords, tokens, cookies, authorization
  headers, session IDs, API keys, private keys.
- `.env` is gitleaks-protected; `.env.example` is the only
  committed sample.

## Reporting a vulnerability

Open a private security issue. We treat boundary regressions as P0
and accept no `--no-verify` / `--admin` shortcuts.
