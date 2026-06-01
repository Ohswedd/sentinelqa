---
title: Safety boundary
description: What SentinelQA refuses to do and why.
status: Stable
---

SentinelQA is for **authorized testing only**. The safety boundary is
non-negotiable; it is enforced in code (config-load, every URL-bearing
tool, CI gates) and in tests (security-policy AST guards run on every
CI pass).

Authority: our product spec, our engineering rules §6.

## Forbidden

The following capabilities are forbidden, will never ship, and any
plugin requesting them is rejected at discovery:

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
- Cookie / session theft
- Data exfiltration
- Phishing flows
- Malware-like behavior

We do not ship features that detection-evade. We do not market
SentinelQA as "undetectable."

## Allowed

- Authorized security assessment
- Safe adversarial testing
- Compliant realism (e.g. transparent UA, transparent `X-SentinelQA-Test-Run` header)
- Audit logs
- Rate limits
- Target allowlists
- Proof-of-authorization gates for destructive modes

## How the boundary is enforced

| Surface                | Mechanism                                                                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Config load            | `SafetyPolicy.enforce` rejects non-local targets without explicit allowlist; refuses destructive modes without a valid proof-of-authorization |
| Every URL-bearing tool | Re-runs `SafetyPolicy.enforce` before issuing any request                                                                                     |
| CLI                    | Reserved flag names (`--stealth`, `--bypass`, `--unbounded`, `--evade*`) refused by the Typer parser                                          |
| Tests                  | `tests/security/test_*` AST guards greps the source for forbidden literals; runs on every CI pass                                             |
| Plugins                | Manifest permission grammar rejects unscoped `fs.write`; subprocess sandbox strips env vars                                                   |

A run blocked by the safety policy exits with code `4` and writes an
audit-log entry. Nothing downstream of the policy ever sees an unsafe
target.

## Reporting a gap

If you find a way to bypass the boundary, open a private security
issue. We treat boundary regressions as P0.
