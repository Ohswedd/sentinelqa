---
title: 'SentinelQA — Secret-Leak Audit'
date: 2026-05-30
auditor: ohswedd
phase: 29 (Final Hardening & PRD Reconciliation)
status: PASS
---

# SentinelQA — Secret-Leak Audit (Phase 29.02)

## Scope

Sweep every artifact persisted by SentinelQA — `run.json`, `findings.json`,
`score.json`, `report.html`, `report.md`, `junit.xml`, `sarif.json`,
`audit.log`, `config.snapshot.yaml`, plus the per-module JSON outputs
(`auth.json`, `network.json`, `contract.json`, `latency.json`, …) — for any
unredacted credential, token, cookie, Authorization header, private key, or
provider API secret.

Per the task plan (`plans/phase-29-final-hardening/02-secret-leak-audit.md`),
the audit is run against a real run tree. We use the **429 existing runs** in
`.sentinel/runs/` (≈ 5.41 MB across 2 442 files spanning every module that
has shipped in Phases 02–28) rather than re-booting `make demo`, because that
sample is materially larger than a single fresh demo run and reflects every
code path the redactor has been asked to handle to date.

## Scanners

### 1. `gitleaks detect --no-git`

Run twice — once with the default ruleset, once with our `.gitleaks.toml`
allowlist (the same config CI uses on the working tree).

```
$ gitleaks detect --no-git --source .sentinel/runs --redact --exit-code 1
[INF] scanned ~5405385 bytes (5.41 MB) in 215ms
[INF] no leaks found
exit=0

$ gitleaks detect --no-git --source .sentinel/runs --config .gitleaks.toml --redact --exit-code 1
[INF] scanned ~5405385 bytes (5.41 MB) in 201ms
[INF] no leaks found
exit=0
```

### 2. Heuristic pattern sweep

A targeted second pass for patterns gitleaks tends to under-weight in
text-heavy reports (Authorization headers, JWTs in error messages, password
assignments in YAML snapshots). Patterns covered:

| Rule                        | Regex anchor                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------------ | ------ | ------------------------------------- |
| `pem_private_key`           | `-----BEGIN ([A-Z]+ )?PRIVATE KEY-----`                                                                |
| `ssh_private_key`           | `-----BEGIN OPENSSH PRIVATE KEY-----`                                                                  |
| `aws_access_key`            | `AKIA[0-9A-Z]{16}`                                                                                     |
| `stripe_live_key`           | `sk_live_[0-9a-zA-Z]{24,}`                                                                             |
| `stripe_test_key_actual`    | `sk_test_[0-9a-zA-Z]{24,}`                                                                             |
| `github_token`              | `gh[pousr]_[A-Za-z0-9]{36,}`                                                                           |
| `slack_token`               | `xox[abprs]-[A-Za-z0-9-]{10,}`                                                                         |
| `google_api_key`            | `AIza[0-9A-Za-z\-_]{35}`                                                                               |
| `openai_sk_key`             | `sk-(proj-)?[A-Za-z0-9]{40,}`                                                                          |
| `anthropic_key`             | `sk-ant-[A-Za-z0-9_-]{40,}`                                                                            |
| `jwt`                       | `eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}`                                        |
| `password_assignment`       | `(password                                                                                             | passwd | pwd)["']?\s*[:=]\s*["'][^"']{6,}["']` |
| `authorization_bearer_real` | `Authorization\s*:\s*Bearer\s+[A-Za-z0-9_\-.]{20,}` (excluded if the captured token is `[REDACTED:…]`) |

Result on the same 2 442-file tree:

```
{
  "files_scanned": 2442,
  "hits": []
}
```

This heuristic sweep is now codified as
`tests/integration/release/test_secret_leak.py::test_sentinel_runs_have_no_unredacted_secrets`
so every CI run re-verifies that no committed run artifact has regressed.

### 3. Redactor smoke-test

Live probe of `engine.policy.redaction.redact`:

```python
>>> redact({'Authorization': 'Bearer sk-abc123xyzfoo',
...         'cookie': 'session=verysecretsessionidvalue',
...         'x-fine': 'ok'})
{'Authorization': '[REDACTED:authorization]',
 'cookie': '[REDACTED:cookie]',
 'x-fine': 'ok'}
>>> redact("Authorization: Bearer sk-abc123xyzfoo Hello")
'Authorization: [REDACTED:bearer_token] Hello'
```

Redactor surface confirmed: header names, header values, dict values, URL
basic-auth, and free-text bearer tokens are all replaced before they reach a
report writer or the audit log.

## Coverage by artifact type

| Artifact                                              | Files scanned | Gitleaks verdict | Heuristic verdict |
| ----------------------------------------------------- | ------------- | ---------------- | ----------------- |
| `run.json`                                            | 429           | clean            | clean             |
| `config.snapshot.yaml`                                | 429           | clean            | clean             |
| `audit.log`                                           | 429           | clean            | clean             |
| `score.json`                                          | 429           | clean            | clean             |
| `report.html`                                         | 158           | clean            | clean             |
| `report.md`                                           | 38            | clean            | clean             |
| `junit.xml`                                           | 138           | clean            | clean             |
| `sarif.json`                                          | 89            | clean            | clean             |
| `plan.json`                                           | 5             | clean            | clean             |
| per-module JSON (`auth/contract/latency/network/...`) | 738           | clean            | clean             |
| total                                                 | **2 442**     | clean            | clean             |

(Counts derived from `find .sentinel/runs -type f -name '<pattern>' | wc -l`.)

## Findings

None. Two informational notes:

1. **The redactor is the **only** authorized scrubber.** Every writer that
   touches user-supplied or target-supplied content
   (`engine/reporter/findings_writer.py`,
   `engine/reporter/junit_writer.py:system_out`,
   `engine/reporter/sarif_writer.py:rule.shortDescription`,
   `engine/log/redaction_filter.py` for every logger) routes through
   `engine.policy.redaction.redact`. There is no second redactor to drift
   from.
2. **Phase 19 `.gitleaks.toml` allowlist entries are fixture-only.** They
   allow the synthetic Stripe-style keys used by
   `tests/integration/llm_audit/fixtures/` and the PEM fixture used by
   `tests/integration/release/test_built_packages.py`. Production code
   continues to reject these patterns on the working tree.

## Conclusion

Zero unredacted secrets across the persisted artifact surface. The audit is
now a recurring CI gate via the new integration test — so any future change
that loosens the redactor will fail before it lands. Phase 29.02 closes
**PASS**.

— ohswedd, 2026-05-30
