# SentinelQA Python SDK — Deprecation Policy

Status: `Stable`

Authority: our engineering rules (SDK rules), §40 (Versioning and release rules), our product spec, ADR-0021.

The SDK's **public surface** is everything you can import via:

- `from sentinelqa import <name>`
- `from sentinelqa.errors import <name>`
- `from sentinelqa.agent import <name>`

Anything else (modules prefixed `_`, internals under `sentinelqa._internal/`)
is **not** part of the public contract. It may change in any release, and
external code that relies on it does so at its own risk.

## What counts as a breaking change

A breaking change is anything that would force a caller of the public
surface to update its code. Examples:

- Removing a name from `__all__`.
- Removing or renaming a public class, function, method, or attribute.
- Changing a method's required signature (removing a positional arg, renaming a keyword-only arg).
- Tightening a return type (e.g. removing a previously-allowed `Optional` wrapping).
- Bumping the major number of any persisted schema (`run.schema.json`, `findings.schema.json`, `score.schema.json`, agent-message envelope).

Adding a new name, adding a keyword-only argument with a safe default,
adding an `async_*` mirror, or returning a subclass of the previously
returned type is **not** breaking — those are additive and ship in
minor releases.

## Process for a breaking change

A breaking change requires all three steps below, in this order:

1. **ADR.** Write a new ADR (or amend an existing one) under `docs/adr/` that documents the new contract, what it replaces, and why the non-breaking path was rejected. Status must be `Accepted` before the change merges.
2. **Deprecation window.** Ship at least one minor release that: - Still exposes the old name. - Emits a `DeprecationWarning` with the new name and a target removal version (e.g. `"X will be removed in 0.4.0; use Y"`). - Updates the public docs.
3. **Removal.** In a later minor (when the SDK is pre-1.0) or major (post-1.0) release, remove the old name. Bump the version accordingly.

During the deprecation window, the API snapshot
(`packages/python-sdk/api-snapshot.json`) must continue to list the
deprecated name. After removal, the snapshot is regenerated; the
accompanying PR must reference the ADR.

## API snapshot gate

`make sdk-api-snapshot` writes the current public surface to
`packages/python-sdk/api-snapshot.json`. CI runs
`tests/unit/sdk/test_api_snapshot.py`, which loads the snapshot and
diffs it against the live `__all__` of every public module. Any
addition or removal fails the test until the snapshot is updated and
an accompanying ADR / minor-release bump lands in the same PR.

This is the same pattern used for the report schema goldens
(`tests/golden/reports/`): the snapshot is the source of truth, and
CI catches accidental contract drift before it ships.

## Pre-1.0 caveat

While the SDK is still pre-1.0 (`0.x.y`), breaking changes are
permitted under the rules above but should be minimized. Every breaking
change between minor versions bumps the **minor** number (`0.1 -> 0.2`).
A `1.0.0` release locks the contract: breaking changes after that
require a major bump (`1.0 -> 2.0`).

## References

- our engineering rules — SDK Rules.
- our engineering rules — Versioning and Release Rules.
- the documentation — SDK requirements: "Stable schema versions."
- our product spec — Versioning.
- ADR-0021 — Public SDK surface.
