# Schema-versioning policy

Status: `Stable`

Authority: `CLAUDE.md` §11 (Artifact rules), `CLAUDE.md` §15.4 (Stable schemas), `CLAUDE.md` §34 (Required ADRs), `CLAUDE.md` §40 (Versioning & release rules), `PRD.md` §18 / §20.

This page is the contract for every machine-readable artifact SentinelQA emits or consumes — `run.json`, `findings.json`, `score.json`, the `RootConfig` accepted by the loader, the healer's `RepairSuggestion`, and the agent-message envelope. Skipping any rule here is a CLAUDE.md violation, not a style nit.

## The constants

The single source of truth lives in `engine/domain/schema.py`. The constants are major-version-only strings:

```python
RUN_SCHEMA_VERSION = "1"
FINDINGS_SCHEMA_VERSION = "1"
SCORE_SCHEMA_VERSION = "1"
CONFIG_SCHEMA_VERSION = "1"
REPAIR_SUGGESTION_SCHEMA_VERSION = "1"
AGENT_MESSAGE_SCHEMA_VERSION = "1"
```

If you change a value here, you've made a breaking change. There is no "minor" or "patch" version on the wire. Backwards-compatible additions DO NOT bump the constant; backwards-incompatible changes DO bump it.

## Rules

1. **Every artifact carries its version.** Every domain model that produces a serialized artifact MUST expose `schema_version: str = Field(default=<constant>)` at its root, AND set the `SCHEMA_VERSION` ClassVar. The Phase 01 gate review checks this for `TestRun`, `Finding`, `QualityScore`, `PolicyDecision`, `RepairSuggestion`, and `Target`.
2. **Single major version per artifact.** No semver-style `1.2.3` versioning. The wire format is "v1, v2, …". A consumer that sees a version it doesn't understand MUST refuse to parse.
3. **Forward compatibility is opt-in.** By default, every artifact uses Pydantic's `extra="forbid"`. Unknown fields are an error. An ADR may carve out an explicit extension point (e.g. a `metadata: dict[str, Any]` field) — without that ADR, do not add one.
4. **Bumping a constant requires:**
   - An ADR explaining the breaking change (CLAUDE.md §34 lists "Report schema" and "Config schema" as triggers).
   - A migration registered in `engine/domain/migrations/__init__.py` (for run/findings/score/repair/agent) or `engine/config/migration.py` (for config), named `migrations/<artifact>_<from>_to_<to>.py` and exposing `def migrate(data: dict[str, Any]) -> dict[str, Any]`.
   - A release-note entry in the changelog.
   - Updated TypeScript counterparts under `packages/shared-schema/`.
5. **Deprecations announce one minor version ahead.** Even though the constant itself is a single integer, planned changes go in the changelog at least one product minor release before the bump, with a migration plan.
6. **CI enforces the contract.** A schema-validation CI step (lands fully in Phase 02 when the JSON Schema dump command ships) checks every committed `*.schema.json` with `check-jsonschema`. Test `tests/unit/domain/test_schema_versions.py` asserts that every artifact-producing model carries the constant at runtime.

## How to add a new artifact

1. Add a new constant to `engine/domain/schema.py` with `SCHEMA_VERSION = "1"`.
2. Add it to `ALL_SCHEMA_VERSIONS`.
3. Add the producing Pydantic model with `SCHEMA_VERSION: ClassVar[str]` and a `schema_version` field defaulted to the constant.
4. Register the model in `engine/domain/jsonschema.py:_MODELS` so `make schemas` emits its JSON Schema.
5. Add a `tests/unit/domain/test_schema_versions.py` assertion that the new model serializes with the constant.
6. Cite this doc in your ADR.

## How to bump an existing artifact

1. Write an ADR explaining what changed and why.
2. Add a migration entry in the relevant `migrations/` registry.
3. Bump the constant in `engine/domain/schema.py`.
4. Update the Pydantic model.
5. Update `tests/unit/domain/test_schema_versions.py` and any golden tests under `tests/golden/`.
6. Update the TypeScript schema in `packages/shared-schema/` to keep parity.
7. Run `make ci` — the schema-validation step (Phase 02+) flags any committed sample that doesn't conform.

## See also

- `engine/domain/schema.py` — constants.
- `engine/domain/migrations/__init__.py` — migration registry.
- `engine/config/migration.py` — config-specific migrations.
- `docs/adr/0005-config-schema.md` — config schema decisions.
- `docs/adr/0006-safety-policy.md` — proof-of-authorization schema.
