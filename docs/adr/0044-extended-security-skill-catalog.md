# ADR-0044: Extended security skill catalog (Phase 32)

## Status

Accepted

<!-- Date: 2026-05-31 -->
<!-- Authors: @ohswedd -->

## Context

The Phase 13 security module landed the OWASP basics (headers, cookies,
CORS, CSRF, safe XSS, IDOR smoke, secret scan, SARIF export). Two
years of community feedback plus the post-MVP review surfaced three
recurring asks:

1. **Standards mapping** — security teams want `cwe_id`, `attack_id`,
   `owasp_api_id` on findings so SARIF dashboards and incident triage
   tools can deep-link to canonical references. Today every Phase-13
   finding category is "SentinelQA jargon".
2. **Wider catalog within the safety boundary** — the Anthropic
   Cybersecurity Skills taxonomy enumerates eight defensive checks that
   fit cleanly inside CLAUDE.md §6 (no exploit weaponisation): JWT
   weaknesses, extended cookie posture, TLS posture, GraphQL safety,
   OWASP API Top-10 BOLA/BFLA, frontend-only-auth deeper probe,
   secret-in-bundle scanning, SSRF / open-redirect surface mapping.
3. **Versioned wire compatibility** — `findings.json` is a stable wire
   format consumed by downstream dashboards; adding the three new
   taxonomy fields without breaking v1 consumers requires a v2 schema
   bump plus a forward-compatible reader path.

PRD §10.7 (Security testing), §10.9 (LLM-code-specific audits), §13
(CLI), §17 (Configuration), §18 (Finding schema) and CLAUDE.md §6
(forbidden capabilities), §26 (Security module rules) frame the work.

## Decision

Phase 32 ships **nine** deliverables under a single ADR:

1. **`FINDINGS_SCHEMA_VERSION` bumped `"1"` → `"2"`** in
   `engine/domain/schema.py`. The `Finding` Pydantic model gains three
   optional fields — `cwe_id`, `attack_id`, `owasp_api_id` — each with
   strict regex validation (`^CWE-\d+$`, `^T\d{4}(\.\d{3})?$`,
   `^API-\d{4}-\d{2}$`). The bump is forward-compatible: v1 documents
   parse cleanly into the v2 model (the new fields default to `None`).
   An explicit `engine.domain.migrations.findings_1_to_2.migrate`
   helper is registered in the `MIGRATIONS` map so callers that need
   to re-stamp a v1 doc as v2 can do it deterministically.

2. **Single source-of-truth mapping** in
   `modules/security/cwe_mapping.py` (and a smaller mirror in
   `modules/api/cwe_mapping.py`) maps every existing Phase-13 + every
   new Phase-32 finding category to canonical taxonomy ids. The
   `findings_from_checks` converter in both modules consults the map
   when an issue's evidence dict omits the ids, so every finding
   ships with a `cwe_id` (and where applicable an `attack_id` and/or
   `owasp_api_id`) without per-check boilerplate.

3. **SARIF taxa emission** in `engine/reporter/sarif_writer.py`:
   `runs[].taxonomies` lists the distinct CWE / ATT&CK / OWASP-API
   identifiers referenced by the finding set with stable per-id help
   URIs (`https://cwe.mitre.org/data/definitions/<n>.html`,
   `https://attack.mitre.org/techniques/<id>/`, OWASP-API editions
   index). Each result that carries a taxonomy id gets a
   `taxa` reference plus a redundant `properties.cwe_id` /
   `properties.attack_id` / `properties.owasp_api_id` pair so
   downstream consumers can pivot without a `toolComponent` lookup.

4. **Eight new check modules** under `modules/security/checks/`:

   - `jwt_weakness.py` (Phase 32.01) — fixed 6-entry HS256 weak-secret
     wordlist, `alg=none` detection, missing/expired `exp`, missing
     `iss`/`aud` for multi-tenant tokens.
   - `cookies.py` (Phase 32.02, extended) — `__Host-` / `__Secure-`
     prefix check, over-broad `Domain` detection, over-broad `Path`
     detection (modulo the `__Host-` carve-out that REQUIRES Path=/).
   - `tls_posture.py` (Phase 32.03) — read-only TLS handshake;
     version / cipher / cert-expiry / HSTS posture.
   - `graphql_safety.py` (Phase 32.04) — fixed 3-query probe set
     (introspection, depth-5, alias bomb) + optional anonymous
     mutation probe (one request per discovered mutation).
   - `api_bola_bfla.py` (Phase 32.05) — replays observed identity-A
     calls under identity B; hard-gated behind
     `security.mode=authorized_destructive` + a non-empty
     `target.proof_of_authorization`; capped at 50 endpoints per run.
   - `frontend_only_auth_deeper.py` (Phase 32.06) — replays observed
     XHR / fetch URLs anonymously; flags 200-with-body responses.
   - `bundle_secrets.py` (Phase 32.07) — streamed JS-bundle scan,
     50 MiB cap, fixed 7-pattern set, redacted match prefixes only.
   - `ssrf_redirect.py` (Phase 32.08) — fixed 6-payload SSRF list +
     2-payload open-redirect list; same destructive-mode gate as
     `api_bola_bfla`.

5. **One CI safety guard** at
   `tests/security/test_no_offensive_checks.py` greps the new modules
   for forbidden tokens (`exploit`, `bypass`, `shellcode`,
   `obfuscate`, `evade`, `captcha_bypass`, `stealth`, etc.) and asserts
   per-module load-bearing invariants: JWT module never loads an
   external wordlist; SSRF module's payload list is a module-level
   `Final[tuple[str, ...]]`; TLS module never sends application-layer
   bytes outside the SSL handshake; GraphQL module's probe shapes are
   a fixed `Final[tuple[str, ...]]`.

## Consequences

- **Positive.**

  - Every security finding now carries a `cwe_id` (and frequently
    `attack_id` / `owasp_api_id`). SARIF dashboards (GitHub
    code-scanning, Defect Dojo, SonarQube) can deep-link to
    `cwe.mitre.org`, `attack.mitre.org`, and the OWASP API editions
    index without custom wiring.
  - The catalog grows from 7 OWASP basics to 15 standards-anchored
    classes, materially expanding the "did we ship a credential by
    accident?" coverage SentinelQA can offer LLM-built apps.
  - The forward-compat v1→v2 reader means existing dashboards that
    persisted v1 `findings.json` keep working; the migration helper
    gives operators an explicit re-stamp path when needed.

- **Negative / trade-off.**

  - Wire format is now v2. Downstream readers that hard-coded
    `schema_version: "1"` (e.g. external SIEMs ingesting `findings.json`
    directly) need to update. The Phase 02 schema-versioning policy
    (`docs/dev/schema-versioning.md`) covers this; the changelog
    entry for v0.8.0 calls it out.
  - The `Finding` JSON Schema's `required` list now includes the three
    new fields. v1 documents validated against the v2 schema will fail;
    consumers re-validating old data must run the v1→v2 migration
    first.
  - The SDK API snapshot (`packages/python-sdk/api-snapshot.json`)
    surfaces three new public model fields. The Phase-16 deprecation
    policy treats `model_fields` additions as backwards-compatible
    surface changes; no public method or class is removed or renamed.

- **Follow-up obligations.**
  - Phase 33 (Supply-Chain & Dependency Audit) is the next phase that
    consumes the new SARIF `taxa` emission; ADR-0044 commits Phase 33's
    findings to surface `cwe_id` from day one. Phase 33's task files
    already enumerate this requirement.
  - The eight new check functions are exposed as importable
    `run_<name>_check(ctx, ...)` entry points behind the existing
    `SecurityCheck` Protocol. Operator-facing CLI subcommands and
    config toggles for each check are an SDK / orchestrator
    surface-area decision and are intentionally **out of scope** for
    this ADR — the catalog adds capability, it does not extend the CLI
    surface. The safety guard in
    `tests/security/test_no_offensive_checks.py` MUST stay green
    regardless of any future wiring.

## Alternatives considered

- **Ship the eight new checks one phase at a time** (32a/32b/32c)
  with three smaller ADRs. Rejected: the work is mechanically
  homogeneous (every check follows the same `SecurityCheck` Protocol),
  the taxonomy mapping in 32.09 is foundational for _every_ other
  check, and a single ADR keeps the safety boundary justification
  in one place.
- **Carry the CWE / ATT&CK ids out-of-band in the `evidence` dict
  instead of bumping the schema.** Rejected: machine consumers
  (SARIF tooling, dashboards) want top-level structured fields, not
  a free-form dict; and `evidence` is per-finding bespoke whereas the
  taxonomy ids are universal.
- **Introduce a separate `taxa` artifact alongside `findings.json`.**
  Rejected: it splits one logical document into two for a single
  optional triple of strings. Doubles the wire-format burden on
  downstream readers for no gain.
- **Vendor parts of the Anthropic Cybersecurity Skills repo to
  reuse exploit primitives.** Rejected outright (CLAUDE.md §6): the
  offensive material in that taxonomy is precisely what SentinelQA's
  safety boundary excludes. We use the taxonomy as a _naming source_,
  not a code dependency.

## References

- PRD section(s):
  - PRD §10.7 (Security testing) — extended with §10.7.1
    "Extended Security Skill Catalog" by this ADR.
  - PRD §10.9 (LLM-code-specific audits).
  - PRD §18 (Finding schema) — v2 fields documented.
- CLAUDE.md rule(s):
  - CLAUDE.md §6 (Non-Negotiable Safety Boundary).
  - CLAUDE.md §11 (Artifact and Data Rules) — schema versioning.
  - CLAUDE.md §24 (Findings Rules) — every finding has evidence and
    now a taxonomy reference.
  - CLAUDE.md §26 (Security Module Rules) — safe-by-default,
    allowlisted targets.
  - CLAUDE.md §34 (Documentation Rules) — Report-schema trigger met.
- External:
  - <https://cwe.mitre.org> — Common Weakness Enumeration.
  - <https://attack.mitre.org> — MITRE ATT&CK technique catalog.
  - <https://owasp.org/API-Security/editions/2023/en/0x11-t10/> —
    OWASP API Top-10 (2023).
  - <https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json>
    — SARIF 2.1.0 schema; `runs[].taxonomies` shape.
- Related ADRs:
  - ADR-0018 (Phase 13 security module).
  - ADR-0042 (multi-provider LLM adapter layer).
  - ADR-0043 (browser-authenticated audits).
