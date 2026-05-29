# sentinelqa — SentinelQA Python SDK

Status: `Stable` (Phase 16)

The official Python SDK for SentinelQA. A typed, agent-friendly facade
over the engine — `Sentinel` loads config, runs the audit lifecycle,
and returns structured results (`AuditResult`, `Finding`,
`ModuleResult`, …) that are safe to ship straight to an LLM context.

## Install

```bash
uv pip install sentinelqa
```

The SDK ships under the workspace and is installed automatically when
you run `make install` at the repo root.

## Basic usage (PRD §14.1)

```python
from sentinelqa import Sentinel

qa = Sentinel(project_path=".")
result = qa.audit(
    url="http://localhost:3000",
    modules=["functional", "accessibility", "performance", "security"],
    safe_mode=True,
)

print(result.quality_score)
print(result.release_decision)
```

## Agent-friendly usage (PRD §14.2)

```python
from sentinelqa import Sentinel

qa = Sentinel(project_path=".", machine_readable=True)

plan = qa.plan(url="http://localhost:3000")
result = qa.run_plan(plan)

if not result.passed:
    for failure in result.failures:
        print(failure.to_agent_message())
```

## Async API

Every long-running method has an `async_<name>` counterpart. The sync
forms are `asyncio.run(self.async_<name>(...))`, so there is exactly
one implementation per method:

```python
import asyncio
from sentinelqa import Sentinel

async def main() -> None:
    qa = Sentinel(project_path=".")
    result = await qa.async_audit(url="http://localhost:3000")
    print(result.quality_score)

asyncio.run(main())
```

## Error handling (PRD §14.4)

Every public exception is a subclass of `SentinelError`, carries a
stable `code` (`E-CFG-001`, `E-SAFE-001`, …) and an `exit_code`
matching the CLI, and exposes a redacted `to_agent_message()` dict:

```python
from sentinelqa import Sentinel, UnsafeTargetError
from sentinelqa.errors import from_dict

qa = Sentinel(project_path=".")
try:
    qa.audit(url="http://example.com")
except UnsafeTargetError as err:
    msg = err.to_agent_message()  # safe to ship to an LLM
    rebuilt = from_dict(msg)      # round-trip back to a typed exception
    assert rebuilt.code == err.code
```

## Agent messages

```python
from sentinelqa.agent import format

# `format(messages, format="ndjson")` returns newline-delimited JSON —
# ideal for piping straight into an LLM context window.
print(format(result.to_agent_messages(), format="ndjson"))
```

## Public surface

Anything you can import via:

- `from sentinelqa import …`
- `from sentinelqa.errors import …`
- `from sentinelqa.agent import …`

is part of the stable contract. Drift is enforced by
`tests/unit/sdk/test_api_snapshot.py` against
`packages/python-sdk/api-snapshot.json`. Breaking changes require a
deprecation window — see [`__deprecation_policy.md`](./__deprecation_policy.md)
and [ADR-0021](../../docs/adr/0021-public-sdk-surface.md).

Internals (`sentinelqa._internal/`, anything prefixed `_`) are not
public and may change without notice between minor versions.

## References

- PRD §14 — Python SDK Specification.
- CLAUDE.md §14 — SDK Rules.
- ADR-0021 — Public SDK surface.
- `docs/user/error-codes.md` — Stable error code reference.
