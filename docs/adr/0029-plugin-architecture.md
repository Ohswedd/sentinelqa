# ADR-0029: Plugin architecture — entry-point discovery, capability/permission declarations, subprocess sandbox

## Status

Accepted

<!-- Date: 2026-05-30 -->
<!-- Authors: @ohswedd -->

## Context

our product spec promises a plugin architecture covering eight kinds: discovery,
scanner, runner, reporter, policy, auth, data-fixture, and
cloud-execution. The release shipped through has every first-party
module hard-wired through `engine.modules.base.SentinelModule` (Phase
10, ADR-0015). For SentinelQA to fulfil our engineering rules("plugin
requirements") and avoid forcing every integration into the monorepo,
a typed third-party surface must exist.

Three constraints shape the design:

1. **our engineering rules** Plugins must not be able to ship stealth/evasion capabilities, bypass safety policy, or escape the per-run artifact directory.
2. **our engineering rules(plugin requirements).** Versioned contracts, capability declarations, permission declarations, safe defaults, and sandboxed execution where possible.
3. **our engineering rules/ §40 versioning + deprecation rules.** Plugins ship with their own semver; the host pins a `PROTOCOL_VERSION`; incompatible plugins are rejected at load.

We considered three alternatives:

- **Class-based registration via Python imports.** Rejected: forces every plugin into a SentinelQA-aware import path; brittle for external distribution.
- **JSON-RPC subprocess for every plugin.** Rejected: kills the in-process composition story for trivial scanners and hurts cold- start latency for `sentinel audit`. We keep subprocess isolation but make it opt-in via the `subprocess.spawn` permission.
- **importlib.metadata entry points + Pydantic manifest.** Chosen: the standard Python plugin pattern, zero new runtime deps, naturally integrates with `pip install` workflows.

## Decision

### Wire format and discovery

- The SDK exposes typed Protocols at `packages/python-sdk/src/sentinelqa/plugins.py` (`PROTOCOL_VERSION` pinned to `1.0.0`, eight `@runtime_checkable` Protocols, a `PluginContext` Protocol, and a `PLUGIN_PROTOCOLS` lookup keyed by `kind`).
- Plugins register a class under the `sentinelqa.plugins` entry-point group: `toml [project.entry-points."sentinelqa.plugins"] my-scanner = "my_pkg.plugin:MyScanner" `
- The host (`engine.plugins.discover`) iterates entry points, instantiates the class (or accepts an already-constructed instance), synthesises a manifest from class-level attributes, validates it, and confirms `isinstance(obj, PLUGIN_PROTOCOLS[kind])`. Failures log and skip — a broken plugin never crashes a run.

### Manifest schema

- Strict Pydantic model at `engine.plugins.manifest.Manifest` (`extra="forbid"`, frozen).
- Mirrored JSON Schema at `packages/shared-schema/plugin-manifest.schema.json` (Draft 2020-12).
- A drift guard (`tests/integration/plugins/test_manifest_schema.py`) round-trips fixture payloads through both and proves they agree.

Required fields: `name` (kebab-case), `version` (semver), `kind`
(enum of eight), `requires_protocol` (PEP 440 specifier). Optional:
`capabilities`, `permissions`, `entry_point`, `description`.

### Capabilities and forbidden list

- Capabilities are free-form strings — but anything overlapping `engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES` (`stealth_automation`, `bot_detection_bypass`, `proxy_rotation_for_evasion`, …) is rejected at load with `PluginCapabilityForbiddenError`.

### Permission grammar

- Permissions follow `<group>.<verb>` or `<group>.<verb>:<scope>`.
- The allow-list is fixed and lives in `engine.plugins.manifest.ALLOWED_PERMISSIONS`: `fs.read`, `fs.write:.sentinel/runs`, `network.outbound`, `subprocess.spawn`, plus scoped prefixes (`fs.read:<path>`, `env.read:<NAME>`).
- **Unscoped `fs.write` is forbidden** — plugins cannot write outside `<run_dir>/plugins/<plugin_name>/`, the only writable area exposed via `PluginContext.artifact_path(name)`.
- `PluginContext` enforces every permission at the call site; overreach raises `PluginPermissionError` (exit code 7).

### Versioning

- Host pins `PROTOCOL_VERSION = "1.0.0"`; plugins declare `requires_protocol = ">=1.0,<2.0"` (or similar).
- Range check uses `packaging.specifiers.SpecifierSet`; an empty spec is treated as "any version" with a load-time warning.
- Bumping the major version of `PROTOCOL_VERSION` requires a new ADR and a deprecation window per our engineering rules

### Subprocess sandbox

- Plugins declaring `subprocess.spawn` can be executed via `engine.plugins.sandbox.run_in_sandbox(...)`, which spawns `python -m engine.plugins.sandbox_worker` in a child process.
- Wire protocol: one line of JSON in (entry-point, granted permissions, payload, run context), one line of JSON out (`ok` + `result` or `error`).
- Child env is filtered to a small fixed allow-list (`PATH`, `HOME`, `TMPDIR`, locale vars, `PYTHONPATH`, `VIRTUAL_ENV`) plus `SENTINEL_*` / `SENTINELQA_*` prefixes plus every `env.read:<NAME>` the manifest declared. Everything else is dropped.
- Default 60s timeout; timeouts surface as `ok=False` rather than blowing up the host.
- OS-level isolation (firejail / bubblewrap) is intentionally OUT of scope here — the contract is process isolation + env redaction. Stronger isolation lands later behind its own ADR if needed.

### CLI surface

- New Typer subapp `sentinel plugins` with three subcommands: - `list` — discovered plugins. - `info <name>` — one manifest. - `validate <path>` — validate a JSON/TOML manifest before publishing.
- JSON mode is supported across all three.

### Exit codes

Plugins funnel through the existing error registry:

- `E-PLG-001` (exit 5) — load-time failures (manifest drift, incompatible protocol, forbidden capability, isinstance failure).
- `E-PLG-002` (exit 7) — runtime failures (`PluginPermissionError`, worker crash).

## Consequences

- Adding new plugin kinds becomes an additive change: declare a new Protocol, add it to `PLUGIN_PROTOCOLS`, add the kind to the JSON Schema enum and Pydantic validator, ship.
- Adding new permissions requires updating `ALLOWED_PERMISSIONS` / `ALLOWED_PERMISSION_PREFIXES` plus the JSON Schema; sensitive new permissions warrant a follow-up ADR.
- The plugin Protocol surface is part of the SDK public API snapshot (`packages/python-sdk/api-snapshot.json`). Breaking changes ship via the deprecation policy at `packages/python-sdk/__deprecation_policy.md`.
- Plugin authors get a documented contract (`docs/dev/plugins.md`, `docs/dev/plugin-permissions.md`) and two reference implementations under `examples/plugins/`.

## Scope notes

ships the plugin loading + validation + sandbox surface and
documents the contract. Whether and how `discover` is wired into
`sentinel audit`'s module scheduler is a separate decision: our product spec +
CLAUDE §22 describe the loader contract, not an automatic-scheduling
guarantee. Any future change that auto-runs discovered scanners as
part of `sentinel audit` MUST ship its own ADR; nothing in this ADR
implies such an integration is planned.

## Alternatives considered

- **Class-based registration via direct Python imports.** Rejected: forces every plugin into a SentinelQA-aware import path; brittle for external distribution and incompatible with `pip install` workflows.
- **JSON-RPC subprocess for every plugin.** Rejected: kills the in-process composition story for trivial scanners and hurts cold- start latency for `sentinel audit`. Subprocess isolation is kept but made opt-in via the `subprocess.spawn` permission.
- **YAML-only manifest with no in-Python attribute extraction.** Rejected: forces plugin authors to maintain a separate manifest file in sync with the Python class, doubling the surface area for drift. The current design lets the loader synthesise a manifest from class-level attributes; the JSON Schema is reserved for external publishing validation (`sentinel plugins validate`).
- **A single `Plugin` Protocol with a `kind` discriminator.** Rejected: would force all callers to runtime-dispatch on `kind` before calling any method. Per-kind Protocols give plugin authors IDE help and let the loader's `isinstance` check be a real type guarantee, not a stringly-typed convention.

## References

- PRD section(s): our product spec (Plugin Architecture), the documentation (Plugin interface), the documentation (Plugin requirements).
- our engineering rules rule(s): our engineering rules(Non-negotiable safety boundary), our engineering rules(Generated Test Rules — referenced via "plugin requirements"), our engineering rules(Required ADR triggers — "Plugin system"), our engineering rules(Versioning and release rules).
- External: PEP 503 (entry points), PEP 440 (version specifiers), the `packaging` library (https://packaging.pypa.io/en/stable/specifiers.html).
- Related ADRs: ADR-0015 (Module contract and functional module — the first-party module Protocol whose pattern the plugin `ScannerPlugin` mirrors), ADR-0021 (Public SDK surface — pinning the snapshot gate the plugin Protocols now extend).
