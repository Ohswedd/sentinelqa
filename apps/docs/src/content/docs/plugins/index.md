---
title: Plugins
description: Ship out-of-tree modules via the sentinelqa.plugins entry-point group.
status: Stable
---

SentinelQA discovers plugins via Python entry points
(`sentinelqa.plugins` group). Each plugin declares a typed manifest
(name, version, kind, capabilities, permissions) and implements one
of the eight public Protocols.

Authority: PRD §22, ADR-0029, CLAUDE.md §6 (permission deny-list).

## Eight protocols

| Protocol               | Purpose                    |
| ---------------------- | -------------------------- |
| `DiscoveryPlugin`      | Custom crawl backend       |
| `ScannerPlugin`        | New audit check            |
| `RunnerPlugin`         | Alternate test executor    |
| `ReporterPlugin`       | New output format          |
| `PolicyPlugin`         | Custom policy gate         |
| `AuthPlugin`           | Authentication strategy    |
| `DataFixturePlugin`    | Test data setup / teardown |
| `CloudExecutionPlugin` | Remote runner backend      |

All Protocols are `@runtime_checkable`; loaded objects are validated
via `isinstance(obj, PLUGIN_PROTOCOLS[kind])`.

## Permission grammar

`<group>.<verb>[:<scope>]`. The allow-list is:

```
fs.read                                      fs.read:<path>
fs.write:.sentinel/runs                      env.read:<NAME>
network.outbound                             subprocess.spawn
```

Unscoped `fs.write` is **rejected**. Plugins requesting forbidden
capabilities (see CLAUDE.md §6) fail discovery.

## Subprocess sandbox

`engine.plugins.sandbox.run_in_sandbox` spawns a fresh Python process
with a filtered env (only `ALWAYS_INHERITED_ENV` + `SENTINEL_*` /
`SENTINELQA_*` prefixes + declared `env.read:<NAME>` pass through).
One JSON line in, one out. 60-second default timeout.

## CLI

```bash
uv run sentinel plugins list
uv run sentinel plugins info my-scanner
uv run sentinel plugins validate ./my-plugin/
```

## Example plugins

Two reference plugins live under `examples/plugins/`:

- `sentinelqa-scanner-example` — HeaderChecker
- `sentinelqa-reporter-example` — CsvReporter

Each ships a `pyproject.toml` with the entry-point declaration and a
README walking through the integration test.
