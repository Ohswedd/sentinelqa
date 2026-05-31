# ADR-0045: Supply-Chain & Dependency Audit module (Phase 33)

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

The Phase 13 security module audits the _running_ application — the
attack surface PRD §10.7 enumerates. Two recurring asks from the
post-MVP review forced us to take the second half of release
confidence seriously:

1. **The build inputs are themselves an attack surface.** A clean run
   against a runtime that ships with a poisoned `lodash` or
   `colors.js` is still a regression — and modern incidents
   (`event-stream`, `ua-parser-js`, `node-ipc`, `xz`) all landed via
   dependency tampering rather than the application code path. PRD
   §10.7 only catches the latter.
2. **Compliance teams want SBOMs.** SPDX / CycloneDX SBOMs are now a
   hard requirement for FedRAMP, SOC 2, the EU Cyber Resilience Act,
   and most enterprise procurement reviews. A release-confidence
   engine that cannot emit an SBOM is not a release-confidence engine
   for those audiences.

CLAUDE.md §6 forbids active exploitation, stealth, and any flavour of
"undetectable" tooling. CLAUDE.md §26 requires safe defaults and
explicit allowlists. The Phase 33 module must therefore land entirely
in defensive / read-only territory. The OSV API is read-only, public,
and documented; Trivy / Grype run against the configured image only
and never iterate registries; the postinstall scanner reads scripts —
it never executes them.

PRD §10.7 (Security), §22 (Plugin architecture — supply-chain checks
could later move behind plugins), §32 (Recommended build order —
supply-chain belongs after the core modules stabilise), CLAUDE.md §6
(no aggressive scanning), §26 (Security module rules), §35
(Dependency rules) frame the work.

## Decision

Phase 33 ships **seven** deliverables under a single ADR:

1. **CycloneDX 1.5 SBOM generation** in `modules/supply_chain/sbom.py`
   plus seven lockfile parsers in `modules/supply_chain/lockfiles.py`
   (`uv.lock`, `poetry.lock`, `Pipfile.lock`, `requirements.txt`,
   `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`). The writer
   emits a deterministic, byte-stable CycloneDX document per lockfile
   plus an aggregate `index.json` under `<run-dir>/sbom/`. A focused
   JSON Schema at
   `packages/shared-schema/external/cyclonedx-1.5.json` captures the
   shape we emit; `tests/integration/modules/supply_chain/
test_sbom_against_examples.py` re-runs `jsonschema.validate` on
   every emitted SBOM as a drift guard.

2. **OSV vulnerability lookup** in `modules/supply_chain/osv.py` that
   reads the SBOM from (1), batches up to 1 000 components per
   `POST /v1/querybatch` call, respects
   `policy.supply_chain.osv.rate_limit_rps`, and maps OSV's CVSS
   bands to SentinelQA severity (≥9.0 critical, ≥7.0 high, ≥4.0
   medium, >0 low, 0 info). When the network is unreachable the
   report records `skipped=True` with a `"OSV unreachable"` reason —
   it never marks the run "passed" or "errored" (Phase 33 README:
   "Offline degradation is skipped, not errored, not passed").
   Findings carry `cwe_id` from the advisory's `database_specific`
   field when present.

3. **Lockfile freshness + manifest drift** in
   `modules/supply_chain/freshness.py`. Age is computed from the
   **most recent** of (filesystem mtime, last git commit touching the
   lockfile) so a fresh clone doesn't read as freshly-edited. Drift
   compares the manifest's direct deps (`package.json`,
   `pyproject.toml`) to the lockfile's resolved package set; findings
   carry `CWE-1357` (Reliance on Unmaintained Third-Party Components).
   Default threshold is 180 days, configurable via
   `policy.supply_chain.max_lockfile_age_days`.

4. **Postinstall hook scanner** in
   `modules/supply_chain/postinstall.py`. Walks every `package.json`
   under `node_modules/` and every Python `setup.py` under
   `venv/` / `.venv/` / `.tox/`. For npm: regex-grep for `curl`,
   `wget`, `nc`, `ncat`, `bash -c`, `sh -c`, `eval`, plus writes to
   `/etc/`, `/usr/`, `/var/`, `/root/`, `/home/`, `~/`, `$HOME`. For
   Python: an AST scan for top-level imports of `subprocess`,
   `urllib.request`, `requests`, `httpx`, `socket`, `os.system`, plus
   direct calls to `subprocess.{run,Popen,call}` / `os.system`.
   Findings carry `CWE-506` (Embedded Malicious Code). The scanner
   never executes the matched code — a grep-guard in
   `tests/security/test_no_offensive_supply_chain.py` keeps
   `subprocess.run(` / `os.system(` out of the scanner source.

5. **Container image scanner adapter** in
   `modules/supply_chain/container.py`. Prefers Trivy when on PATH;
   falls back to Grype. When neither is installed the report is
   `skipped` with an info-severity recommendation — never silently
   passed. The scanner runs ONLY against
   `policy.supply_chain.container.image`; it never pulls, never
   iterates a registry, never scans random images. Output is capped
   at `policy.supply_chain.container.max_findings` (default 200) so a
   CVE-heavy base image cannot flood the report.

6. **SPDX license audit** in `modules/supply_chain/licenses.py`. For
   every SBOM component, resolve the declared license (npm carries it
   in the lockfile; PyPI components default to "unknown" because the
   alternative — fetching PyPI metadata over the network — would
   break the offline guarantee). Components are classified as
   `allow` / `deny` / `unknown` against
   `policy.supply_chain.licenses`. Defaults: allow `Apache-2.0`,
   `MIT`, `BSD-3-Clause`, `BSD-2-Clause`, `ISC`, `Python-2.0`; deny
   `GPL-3.0-only`, `AGPL-3.0-only`, `AGPL-3.0-or-later`; unknown
   severity `low`.

7. **`sentinel supply-chain` CLI + config block.**
   `apps/cli/src/sentinel_cli/commands/supply_chain_cmd.py` exposes
   the top-level command plus two sub-surfaces:
   `sentinel supply-chain sbom --out <dir>` (SBOM only) and
   `sentinel supply-chain osv --sbom <path>` (OSV lookup against an
   existing SBOM). Exit codes follow the canonical grid
   (`0 / 1 / 2 / 4 / 5 / 6`). A new
   `engine.config.schema.SupplyChainConfig` nests under `PolicyConfig`
   so users opt in / out per check via
   `policy.supply_chain.<check>.enabled`. Default state is "every
   check on with conservative thresholds" — operators have to
   actively _disable_ a check to drop it.

## Consequences

- A new `modules/supply_chain/` package becomes part of the wheel
  build (`modules/pyproject.toml` glob updated).
- The default `policy:` config block expands; the example config in
  `sentinel.config.yaml.example` documents every knob.
- New SARIF rule ids `SUP-OSV-VULNERABLE-DEP`,
  `SUP-FRESH-STALE-LOCKFILE`, `SUP-FRESH-MANIFEST-DRIFT`,
  `SUP-POSTINSTALL-NETWORK`, `SUP-POSTINSTALL-FS-WRITE`,
  `SUP-POSTINSTALL-PYTHON-EXEC`, `SUP-CONTAINER-CVE`,
  `SUP-CONTAINER-SCANNER-NOT-INSTALLED`, `SUP-LICENSE-DENY`,
  `SUP-LICENSE-UNKNOWN` are registered with the SARIF rule registry
  so downstream dashboards can resolve them to help URIs.
- The vendored CycloneDX 1.5 JSON Schema is a focused subset of the
  official spec; the upstream schema (~9 000 lines, many optional
  fields we don't emit) is intentionally NOT redistributed. The drift
  guard re-validates every emitted SBOM against the subset and
  documents the relationship.
- Findings reuse the Phase 32 v2 schema fields (`cwe_id`,
  `attack_id`, `owasp_api_id`) so the new supply-chain findings are
  taxonomy-aware out of the box — no schema bump needed for Phase 33.
- The container scanner remains opt-in by configuration but is
  enabled by default in the schema; the no-image + no-scanner paths
  both downgrade to `skipped` so a CI run without Trivy / Grype
  doesn't fail spuriously.
- No new third-party Python deps are added. The implementation reuses
  `httpx` (Phase 30 dep), `tomllib` (stdlib), `yaml` (already a
  transitive dep), and `jsonschema` (Phase 03 dep).

## Alternatives considered

- **Use `pip-audit` / `npm audit` directly via subprocess.** Rejected
  for three reasons: (i) shipping a Python wrapper around two
  ecosystem-specific tools recreates Phase 13's `sec-deps-vulnerable`
  surface rather than adding new coverage; (ii) `npm audit` requires
  network and uses npm's own (often slower) vulnerability database;
  (iii) the unified OSV API gives one upstream and covers both
  ecosystems plus Go, Rust, Ruby, Maven, Packagist — future
  ecosystem support is one parser away.
- **Vendor the full official CycloneDX 1.5 schema.** Rejected as
  redistribution scope creep — the official schema has many optional
  fields we don't emit and shifting versions would require a Phase
  33+ ADR each time. The focused subset captures everything we
  produce and is documented as such.
- **Auto-install Trivy / Grype.** Rejected: SentinelQA never installs
  third-party scanners (CLAUDE.md §35). Operators choose their
  scanner; we adapt to whatever is on PATH.
- **Run `pip install` / `npm install` in a sandbox and observe.**
  Rejected as out-of-scope dynamic analysis — the static scan covers
  the same patterns without the cost or risk of running attacker
  code (CLAUDE.md §6 explicitly forbids that approach).
- **Make `policy.supply_chain` a top-level block rather than nesting
  under `policy:`.** Rejected for consistency: `policy:` already
  owns every release-gate threshold and per-integration toggle.
  Nesting keeps the cognitive map flat.

## References

- Phase 33 README — `plans/phase-33-supply-chain/README.md`
- Phase 33 task files — `plans/phase-33-supply-chain/0[1-7]-*.md`
- CycloneDX 1.5 spec — https://cyclonedx.org/specification/overview/
- OSV API — https://google.github.io/osv.dev/post-v1-querybatch/
- Trivy — https://aquasecurity.github.io/trivy/
- Grype — https://github.com/anchore/grype
- CWE-506 (Embedded Malicious Code) — https://cwe.mitre.org/data/definitions/506.html
- CWE-1357 (Reliance on Unmaintained Third-Party Components) — https://cwe.mitre.org/data/definitions/1357.html
- PRD §10.7, §22, §32; CLAUDE.md §6, §26, §35
