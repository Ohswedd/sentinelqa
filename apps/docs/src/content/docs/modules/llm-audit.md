---
title: LLM-Code audit module
description: Detect failure modes specific to AI-generated applications.
status: Stable
---

`sentinel llm-audit` looks for the specific failure modes that
LLM-generated apps tend to ship: dead buttons, fake routes,
mock-data shipped to production, frontend-only auth, hardcoded
credentials, missing CRUD edges, missing loading / error states.

This module is the SentinelQA differentiator.

.

## Sixteen detectors

```
LLM-DEAD-BTN LLM-INCOMPLETE-CRUD
LLM-FAKE-ROUTE LLM-UI-ONLY-AUTH (critical)
LLM-FAKE-ENDPOINT LLM-HARDCODED-CRED
LLM-MOCK-DATA-SHIPPED LLM-CLIENT-SECRET-STORAGE
LLM-FORM-NO-SUBMIT LLM-NO-LOADING-STATE
LLM-NO-ERROR-STATE LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS
LLM-VALIDATION-MISMATCH-FRONTEND-MISSING
LLM-PLACEHOLDER-TEXT LLM-CONSOLE-ERROR-IGNORED
LLM-UNHANDLED-PROMISE
```

## Redaction

Hardcoded-credential snippets are double-redacted before persistence:
the matched span is replaced with `[REDACTED:hardcoded_credential]`,
then the line passes through `engine.policy.redaction.redact`. A test
asserts no literal credential survives in findings.

## Report differentiator

The HTML reporter (`engine.reporter.html_writer`) renders a dedicated
"LLM-Code Audit" section. The PR-comment poster emits a matching
Markdown table. Both stay silent when the module has nothing to say.

## CLI

```bash
uv run sentinel llm-audit --url http://127.0.0.1:5001
```
