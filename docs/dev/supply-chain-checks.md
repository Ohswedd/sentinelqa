# Supply-Chain & Dependency Audit — Phase 33

This document is the operator-facing reference for the
`sentinel supply-chain` command and the underlying
`modules.supply_chain` package (Phase 33, the documentation.3, ADR-0045).

Every check is **defensive / read-only**. our engineering rules
stealth, evasion, fingerprint spoofing, or aggressive scanning;
our engineering rules
both: the OSV adapter only ever talks to `api.osv.dev`; the
container scanner runs only against the configured image; the
postinstall scanner reads scripts — it never executes them.

## Quickstart

```bash
sentinel supply-chain --url http://localhost:3000
sentinel supply-chain sbom --out .sentinel/sbom
sentinel supply-chain osv --sbom .sentinel/sbom/index.json
```

Exit codes follow the canonical grid (`engine/errors/codes.py`):

| Code | Meaning                                                                  |
| ---: | ------------------------------------------------------------------------ |
|    0 | All checks completed; no high/critical findings.                         |
|    1 | Quality gate failed (high/critical findings, or module is `incomplete`). |
|    2 | Invalid config or CLI usage.                                             |
|    4 | Safety policy blocked the target.                                        |
|    5 | A required tool was missing (the top-level command never raises 5;       |
|      | the container check downgrades to `skipped`).                            |
|    6 | The runner failed to execute.                                            |

## The six checks

| Check         | Source                                | CWE      | Findings rule id                          |
| ------------- | ------------------------------------- | -------- | ----------------------------------------- |
| `sbom`        | `modules/supply_chain/sbom.py`        | —        | (no findings; emits CycloneDX docs)       |
| `osv`         | `modules/supply_chain/osv.py`         | per-CVE  | `SUP-OSV-VULNERABLE-DEP`                  |
| `freshness`   | `modules/supply_chain/freshness.py`   | CWE-1357 | `SUP-FRESH-STALE-LOCKFILE`,               |
|               |                                       |          | `SUP-FRESH-MANIFEST-DRIFT`                |
| `postinstall` | `modules/supply_chain/postinstall.py` | CWE-506  | `SUP-POSTINSTALL-NETWORK`,                |
|               |                                       |          | `SUP-POSTINSTALL-FS-WRITE`,               |
|               |                                       |          | `SUP-POSTINSTALL-PYTHON-EXEC`             |
| `container`   | `modules/supply_chain/container.py`   | per-CVE  | `SUP-CONTAINER-CVE`,                      |
|               |                                       |          | `SUP-CONTAINER-SCANNER-NOT-INSTALLED`     |
| `licenses`    | `modules/supply_chain/licenses.py`    | —        | `SUP-LICENSE-DENY`, `SUP-LICENSE-UNKNOWN` |

## Configuration

The full config block lives under `policy.supply_chain` in
`sentinel.config.yaml`. Defaults match the Phase 33 README — "every
check on with conservative thresholds". See
`sentinel.config.yaml.example` for the worked YAML.

| Key                                               | Default               | Purpose                                                      |
| ------------------------------------------------- | --------------------- | ------------------------------------------------------------ |
| `policy.supply_chain.max_lockfile_age_days`       | `180`                 | Freshness threshold (CWE-1357).                              |
| `policy.supply_chain.sbom.enabled`                | `true`                | Emit a CycloneDX 1.5 SBOM.                                   |
| `policy.supply_chain.osv.enabled`                 | `true`                | Query OSV. `false` → `skipped` with explicit reason.         |
| `policy.supply_chain.osv.api_base`                | `https://api.osv.dev` | Override only for air-gapped mirrors.                        |
| `policy.supply_chain.osv.rate_limit_rps`          | `5.0`                 | Protects the OSV public endpoint.                            |
| `policy.supply_chain.osv.request_timeout_seconds` | `30.0`                | Per-request HTTP timeout.                                    |
| `policy.supply_chain.freshness.enabled`           | `true`                | Age + manifest-drift check.                                  |
| `policy.supply_chain.postinstall.enabled`         | `true`                | npm + Python postinstall scanner.                            |
| `policy.supply_chain.container.enabled`           | `true`                | Trivy / Grype adapter (`skipped` when neither is installed). |
| `policy.supply_chain.container.image`             | `null`                | `null` → check is skipped. Set to a digest-pinned image.     |
| `policy.supply_chain.container.max_findings`      | `200`                 | Cap to keep CVE-heavy reports tractable.                     |
| `policy.supply_chain.licenses.enabled`            | `true`                | SPDX license audit.                                          |
| `policy.supply_chain.licenses.allow`              | (see config)          | SPDX allowlist; empty → no whitelisting policy.              |
| `policy.supply_chain.licenses.deny`               | (see config)          | SPDX denylist; deny wins on overlap.                         |
| `policy.supply_chain.licenses.unknown_severity`   | `low`                 | Severity for components with no declared license.            |

## SBOM generation

Detected lockfiles → one CycloneDX 1.5 JSON each plus an aggregate
`<run-dir>/sbom/index.json`. Seven lockfile shapes are supported:

- **Python:** `uv.lock`, `poetry.lock`, `Pipfile.lock`, `requirements.txt`
- **Node:** `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`

Outputs are **byte-stable** — the CycloneDX `serialNumber` is a
UUID v5 over `(lockfile-path, sorted name@version list)` so two
runs against the same inputs emit byte-identical SBOMs. A malformed
lockfile records `parse_error` on its `SbomLockfileResult` and the
run continues with the others.

## OSV lookup

OSV is the unified upstream for Python (PyPI), Node (npm), Go, Rust,
Ruby, Maven, and Packagist advisories. We batch up to 1 000
components per `POST /v1/querybatch` call (the OSV-documented cap)
and back off via a token-bucket rate limit.

CVSS bands map to severity as follows:

| CVSS v3 band | Severity   |
| ------------ | ---------- |
| ≥ 9.0        | `critical` |
| ≥ 7.0        | `high`     |
| ≥ 4.0        | `medium`   |
| > 0.0        | `low`      |
| 0.0          | `info`     |
| (missing)    | `medium`   |

When the network is unreachable the report records
`skipped=True` with reason `"OSV unreachable: <exception>"`. The
audit log captures the same. **The run never marks itself "passed"
against an unreachable OSV.**

## Postinstall scanner — patterns

### npm (`node_modules/**/package.json`)

The scanner inspects the `scripts.{preinstall,install,postinstall,
prepublishOnly,prepublish}` fields. Matched substrings:

| Pattern                                                                | Severity | Notes                                               |
| ---------------------------------------------------------------------- | -------- | --------------------------------------------------- |
| `curl`                                                                 | `high`   | Network call during install.                        |
| `wget`                                                                 | `high`   | Same.                                               |
| `nc` / `ncat`                                                          | `high`   | Out-of-band channel.                                |
| `bash -c` / `sh -c`                                                    | `medium` | Indirection — often a wrapper for one of the above. |
| `eval`                                                                 | `medium` | Indirect code execution.                            |
| Writes to `/etc/`, `/usr/`, `/var/`, `/root/`, `/home/`, `~/`, `$HOME` | `medium` | Out-of-package fs writes.                           |

### Python (`setup.py` reachable under `venv/`, `.venv/`, `.tox/`)

The scanner is an AST walk; we never `import` the target file.

| Trigger                                              | Severity | Notes                                           |
| ---------------------------------------------------- | -------- | ----------------------------------------------- |
| `import subprocess`                                  | `high`   | Subprocess in setup.py means install-time exec. |
| `import urllib.request` / `from ... import urlopen`  | `medium` | Network during install.                         |
| `import requests` / `import httpx` / `import socket` | `medium` | Same.                                           |
| Top-level call to `os.system(`                       | `high`   | Direct shell-out.                               |
| Top-level call to `subprocess.{run,Popen,call}(`     | `high`   | Same.                                           |

The grep guard at
`tests/security/test_no_offensive_supply_chain.py` enforces that the
scanner module never invokes `subprocess.run(` / `os.system(` itself
— it strictly reads.

## Container scanner

Trivy is preferred over Grype because its CVSS metadata is richer.
The adapter looks for either binary on `PATH`; when neither is
present the report is `skipped` with
`SUP-CONTAINER-SCANNER-NOT-INSTALLED` (severity `info`) and the
finding's recommendation links to both tools' install pages.

The scanner runs ONLY against
`policy.supply_chain.container.image`. We never:

- pull arbitrary images,
- iterate over a registry,
- scan running containers,
- pass `--ignore-policy` / `--insecure` / auth overrides.

Findings are capped at
`policy.supply_chain.container.max_findings` (default 200), sorted
critical → high → medium → low → info before the cap is applied.

## License audit

For each SBOM component, the resolver returns the declared SPDX
id(s). npm components carry the field directly in the lockfile;
PyPI components are intentionally license-less in the SBOM because
the alternative — fetching PyPI metadata over the network — would
break Phase 33's offline guarantee. Operators who need PyPI
licenses today should declare them in the project's own SBOM
extension.

| Verdict   | Severity                                                        | Rule id               |
| --------- | --------------------------------------------------------------- | --------------------- |
| `allow`   | (no finding emitted)                                            | —                     |
| `deny`    | `high`                                                          | `SUP-LICENSE-DENY`    |
| `unknown` | `policy.supply_chain.licenses.unknown_severity` (default `low`) | `SUP-LICENSE-UNKNOWN` |

`deny` wins on overlap with `allow` — if a license appears on both
lists, the audit is conservative and flags it.

## Safety boundary

The forbidden-token grep at
`tests/security/test_no_offensive_supply_chain.py` keeps these
literals out of `modules/supply_chain/` and the CLI:

- `exploit`, `shellcode`, `obfuscate`, `evade`, `stealth`, `captcha_bypass`, `deobfuscate`.

The same test verifies that:

- `modules/supply_chain/postinstall.py` never invokes `subprocess.run(` / `subprocess.Popen(` / `subprocess.call(` / `os.system(` — the scanner reads only.
- `modules/supply_chain/container.py` never contains `docker pull`, `image inspect`, or `--privileged` directives.

## Related references

- ADR-0045 (`docs/adr/0045-supply-chain-module.md`).
- Phase 33 README ().
- CycloneDX 1.5 — https://cyclonedx.org/specification/overview/
- OSV API — https://google.github.io/osv.dev/post-v1-querybatch/
- Trivy — https://aquasecurity.github.io/trivy/
- Grype — https://github.com/anchore/grype
