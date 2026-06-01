# Plugin permissions reference

Status: `Stable`

Authority: the documentation, our engineering rules-0029. Wire format pinned by
`packages/shared-schema/plugin-manifest.schema.json`.

A plugin's manifest declares the runtime permissions it intends to
use. The host hands the plugin a `PluginContext`; any call requiring
an undeclared permission raises `PluginPermissionError` (exit code 7).

## Permission grammar

```text
<group>.<verb> # e.g. "fs.read", "network.outbound"
<group>.<verb>:<scope> # e.g. "fs.read:/srv", "env.read:DATABASE_URL"
```

Anything that does NOT match this pattern fails manifest validation.
Permissions must also be on the host's allow list (below) — declaring
an unknown permission is a load-time failure.

## Allow list

| Permission                | What it grants                                                            |
| ------------------------- | ------------------------------------------------------------------------- |
| `fs.read`                 | `context.read_text(path)` — read any file accessible to the host process. |
| `fs.read:<absolute-path>` | Scoped read; treated as "any read" for the unscoped check.                |
| `fs.write:.sentinel/runs` | `context.artifact_path(name)` — write under `<run_dir>/plugins/<name>/`.  |
| `network.outbound`        | Plugin may make outbound HTTP/network calls (subject to safety policy).   |
| `subprocess.spawn`        | Required for plugins launched inside the JSON-over-stdio sandbox.         |
| `env.read:<NAME>`         | `context.env("NAME")` returns `os.environ[NAME]` (sandbox inherits NAME). |

Permissions NOT on this list are rejected at manifest validation.
Notably, **unscoped `fs.write` is forbidden** — plugins cannot write
anywhere except their own per-run subdir, which keeps audits from
leaking artifacts into a project's source tree (our engineering rules§22).

## How enforcement works

The host constructs a `PluginContextImpl` per call. Every concrete
method on the context begins with
`self.require("<permission>")`; missing permissions raise:

```python
ctx = build_plugin_context( plugin_name="my-scanner", run_id="RUN-...", target_url="http://localhost", run_dir=Path("/tmp/run"), config_snapshot={}, granted_permissions=frozenset({"fs.read"}),
)

ctx.artifact_path("out.json") # raises PluginPermissionError
```

The same pattern holds inside the subprocess sandbox: the worker
constructs the same `PluginContextImpl` from the granted set, so a
plugin can't escape its declared permissions by running in a sandbox.

## Path-traversal guard

`context.artifact_path(name)` rejects:

- Absolute paths (`/etc/passwd`).
- Paths containing `..` (`../../escape.txt`).

Both raise `PluginPermissionError` even when `fs.write:.sentinel/runs`
was granted. Subdirectories under the plugin's per-run dir are
permitted and created on demand.

## Env-var policy

The sandbox strips the child's environment to:

- A fixed set (`PATH`, `HOME`, `TMPDIR`, `LANG`, `PYTHONPATH`, `VIRTUAL_ENV`, plus a few locale/Python flags).
- Anything matching `SENTINEL_` / `SENTINELQA_` prefixes.
- Every `env.read:<NAME>` value the manifest declared.

Anything else is dropped. This means secrets that the host process
needs (`AWS_SECRET_KEY`, `GITHUB_TOKEN`, …) never reach the plugin
unless its manifest specifically asks for them by name.

## Forbidden capabilities

Capabilities are validated against
`engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES`. Any
plugin declaring one of these is rejected at load:

```text
bot_detection_bypass captcha_bypass captcha_solving
stealth_automation fingerprint_evasion fingerprint_spoofing
credential_stuffing session_theft cookie_theft
data_exfiltration spam_automation platform_manipulation
phishing proxy_rotation_for_evasion
rate_limit_bypass unauthorized_exploit
destructive_against_public undetectable_mode
```

This list grows over time; plugins should NEVER include a capability
that exists primarily to evade detection, bypass safety controls, or
attack third-party platforms.

## Drift checks

`tests/integration/plugins/test_permissions.py` and the security
guard `tests/integration/plugins/test_discovery.py` run on every CI
pass to ensure:

- Unknown permissions are rejected.
- `fs.write` outside `.sentinel/runs` is rejected.
- Forbidden capabilities are rejected at load.
- `artifact_path` confines writes under the run dir.

If you add a new permission token, you must:

1. Add it to `ALLOWED_PERMISSIONS` (or `ALLOWED_PERMISSION_PREFIXES`) in `engine/plugins/manifest.py`.
2. Update the wire schema at `packages/shared-schema/plugin-manifest.schema.json`.
3. Update this document.
4. Open an ADR if the new permission grants access to anything sensitive.
