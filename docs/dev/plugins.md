# Writing a SentinelQA plugin

Status: `Stable`

Authority: PRD §22 (Plugin architecture), CLAUDE.md §22, ADR-0029
(Plugin architecture — entry-point discovery, capability/permission
declarations, subprocess sandbox).

SentinelQA is built so first-party modules and third-party plugins
share the same contract. A plugin is a Python class registered under
the `sentinelqa.plugins` entry-point group that implements one of the
eight Protocols exported from `sentinelqa.plugins`.

## The eight plugin kinds

| `kind`            | Protocol               | Lives at                              |
| ----------------- | ---------------------- | ------------------------------------- |
| `discovery`       | `DiscoveryPlugin`      | replaces / augments crawling          |
| `scanner`         | `ScannerPlugin`        | runs an audit, returns `ModuleResult` |
| `runner`          | `RunnerPlugin`         | replaces the local/Docker test runner |
| `reporter`        | `ReporterPlugin`       | writes one or more report formats     |
| `policy`          | `PolicyPlugin`         | evaluates release decision            |
| `auth`            | `AuthPlugin`           | acquires test credentials             |
| `data_fixture`    | `DataFixturePlugin`    | seeds + tears down test data          |
| `cloud_execution` | `CloudExecutionPlugin` | submits runs to a remote service      |

Every Protocol declares the same four required attributes:

```python
class MyScanner:
    kind = "scanner"           # one of the eight strings above
    name = "my-scanner"        # lowercase kebab-case, unique
    version = "0.1.0"          # plugin's own semver
    capabilities = frozenset({"audit"})
    permissions = frozenset({"network.outbound"})
    requires_protocol = ">=1.0,<2.0"
```

`requires_protocol` is a PEP 440 specifier against the host's
`sentinelqa.plugins.PROTOCOL_VERSION` (currently `1.0.0`). Bumping the
major version of `PROTOCOL_VERSION` requires an ADR and a deprecation
window (CLAUDE.md §40).

## Packaging

Use any Python build backend (`hatchling`, `setuptools`, `flit`, …).
The only requirement is the entry-point group:

```toml
# pyproject.toml
[project.entry-points."sentinelqa.plugins"]
my-scanner = "my_pkg.plugin:MyScanner"
```

Install your plugin into the same environment as `sentinel`:

```bash
pip install -e .
sentinel plugins list
```

## Lifecycle

The host calls your plugin once per audit run:

```python
def run(self, context: PluginContext) -> ModuleResult:
    # context.run_id              — stable run identifier
    # context.target_url          — already safety-checked
    # context.run_dir             — per-run artifact directory
    # context.config_snapshot     — read-only loaded config
    # context.has_permission(...) — check before risky calls
    ...
```

The exact method signature depends on the plugin kind — see the
Protocol definitions in `packages/python-sdk/src/sentinelqa/plugins.py`.

## Capabilities vs permissions

- **Capabilities** are free-form tags describing what your plugin
  _is_. They surface in `sentinel plugins info` and let users filter
  plugin lists. Any string is accepted EXCEPT those in
  `engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES`
  (`stealth_automation`, `bot_detection_bypass`, …). Declaring one of
  those fails the load (CLAUDE.md §6).

- **Permissions** are runtime grants enforced by `PluginContext`. See
  `docs/dev/plugin-permissions.md` for the full table. Permissions
  follow the grammar `<group>.<verb>` or `<group>.<verb>:<scope>`.

## Sandboxing

Plugins that declare `subprocess.spawn` or `network.outbound` are
launched in a child interpreter via `engine.plugins.sandbox.run_in_sandbox`:

- The child sees only the env vars in `ALWAYS_INHERITED_ENV` plus any
  `env.read:<NAME>` the manifest declared.
- Communication is one line of JSON in and one line of JSON out.
- Failures (timeouts, exceptions) surface as a `SandboxOutcome` with
  `ok=False` so the orchestrator can continue without the plugin.

Pure scanners (no subprocess, no outbound network) run in-process —
the sandbox is opt-in based on what the manifest declared.

## Discovery + validation

When the host calls `engine.plugins.discover()` it:

1. Iterates `importlib.metadata.entry_points(group="sentinelqa.plugins")`.
2. Loads each target (class or instance).
3. Synthesises a manifest from class-level attributes.
4. Rejects forbidden capabilities (CLAUDE.md §6).
5. Rejects incompatible `requires_protocol`.
6. Verifies the loaded object passes
   `isinstance(obj, PLUGIN_PROTOCOLS[kind])`.

Failures log and skip — the run continues without the broken plugin.
Use `sentinel plugins list --show-errors` to see what was rejected.

## CLI surface

```bash
sentinel plugins list                # discovered plugins
sentinel plugins info <name>         # one plugin's manifest
sentinel plugins validate <path>     # validate a JSON/TOML manifest
```

JSON output is available on all three:

```bash
sentinel --json plugins list
```

## Reference plugins

Two reference plugins live under `examples/plugins/`:

- `sentinelqa-scanner-example` — a `ScannerPlugin` that checks one
  HTTP header.
- `sentinelqa-reporter-example` — a `ReporterPlugin` that writes a
  CSV summary.

Copy either as a starting point.

## Versioning + deprecation

Plugin protocol versioning follows the same rules as every other
public SentinelQA contract (CLAUDE.md §40):

- Additive changes (new optional fields, new Protocol kinds) bump
  minor.
- Breaking changes (changed method signatures, renamed attributes,
  removed kinds) bump major AND require an ADR.

A plugin that declares `requires_protocol: ">=1.0,<2.0"` is
guaranteed to keep loading until the host reaches `2.0.0` — at which
point the next major may break it (with the ADR-mandated deprecation
window).
