# ADR-0008: Report schemas and reporter pipeline

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

CLAUDE.md §11 demands an isolated artifact tree per run; §38 demands every
report be machine-readable, schema-stable, and versioned; §24 demands every
finding be evidence-backed. PRD §18 names the entities, §19 the score, §20
the evidence/reporting contract, §21 the CI handshake. Phase 03's job is
to lock the wire formats SentinelQA emits before any module phase (05+)
fills them in, so later phases write against frozen schemas rather than
inventing one each.

Two concrete failure modes drove the decision:

1. **Silent schema drift.** Without per-format goldens + meta-schema checks
   in CI, a one-character rename in a Pydantic model leaks into every
   downstream consumer (GitHub code-scanning, Jenkins JUnit, our own
   Python SDK in Phase 16, the MCP agent surface in Phase 18). The
   compounding cost of recalling those formats far exceeds the cost of
   getting them right once.
2. **Secrets in reports.** Reports run through redaction at the writer
   boundary but the boundary itself is easy to forget when a new format is
   added. The pipeline must redact by construction (every writer goes
   through `ArtifactDirectory.write_json` / `write_text`, both of which
   call `engine.policy.redaction.redact`).

## Decision

Phase 03 ships six writers behind a single `Reporter` dispatcher
(`engine/reporter/dispatcher.py`). Every writer:

- Persists to a **versioned schema** under `packages/shared-schema/`. The
  schema files own the contract; the writers, the goldens, and the
  property tests reference them.
- Passes payloads through the redaction layer at the artifact-directory
  boundary, never directly to `open()`.
- Has at least one **golden test** per interesting state, locked
  byte-for-byte. `make update-goldens` is the only sanctioned way to
  regenerate them; the diff in the follow-up commit is the audit trail.
- Has **schema validation** wired into CI: every committed `*.schema.json`
  validates against its meta-schema; every golden validates against its
  schema; the SARIF goldens validate against the vendored official
  schema (draft-04).
- Has **hypothesis property tests** (slow tier) that generate randomized
  `Finding` collections and prove the writer always produces a valid
  document.

Wire-format ownership:

| Artifact        | Schema                                                        | Writer                               | Notes                                                        |
| --------------- | ------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------ |
| `run.json`      | `packages/shared-schema/run.schema.json`                      | `engine/reporter/run_writer.py`      | Always written. `schema_version=1`. SHA-256 `config_digest`. |
| `findings.json` | `packages/shared-schema/findings.schema.json`                 | `engine/reporter/findings_writer.py` | Refuses medium+ findings without evidence (PRD §20).         |
| `score.json`    | `packages/shared-schema/score.schema.json`                    | `engine/reporter/score_writer.py`    | Deterministic float formatting (2-decimal `total`).          |
| `junit.xml`     | `packages/shared-schema/external/junit.xsd`                   | `engine/reporter/junit_writer.py`    | Surefire subset; lxml XSD validation in CI.                  |
| `sarif.json`    | `packages/shared-schema/external/sarif-2.1.0.json` (official) | `engine/reporter/sarif_writer.py`    | Rule registry; `Draft4Validator` in CI.                      |
| `report.md`     | _(no formal schema)_                                          | `engine/reporter/markdown_writer.py` | Backslash-escapes every Markdown control char.               |

The dispatcher is wired into the lifecycle's `GENERATE_REPORTS` step.
`run.json` is **always** emitted regardless of `config.report.formats`
because it is the canonical lifecycle record; other formats are opt-in.
`json` (config-level) expands to run + findings + score. `html` is a
Phase-15 placeholder. Each emitted artifact writes one
`artifact_emitted` line to the audit log.

Short-circuit lifecycle exits (`unsafe_blocked`, `dry_run`) bypass
`generate_reports` but still write `run.json` through
`engine.reporter.run_writer.write_run` so every run — happy path or
short-circuit — uses the same wire format. The short-circuit paths
do not emit findings/score/junit/sarif/markdown because no module
ran; their `artifact_paths.audit_log` slot is populated and every
other slot is `null`.

`ReporterPlugin` is shipped as a `Protocol` so Phase 24 can replace the
ad-hoc dispatch with entry-point discovery without changing the writer
contracts.

## Consequences

- **Positive:** wire-format drift is impossible without a deliberate
  `make update-goldens` and a follow-up commit. Reviewers see the diff.
- **Positive:** every report includes a `schema_version` field at its
  root, so future versions can ship a migrator without breaking older
  consumers. The constants live in
  `engine/domain/schema.py`; ADR-0005 already governs how they change.
- **Positive:** SARIF + JUnit + Markdown ride the same dispatcher, so
  Phase 17 (CI integration) configures formats in one place
  (`config.report.formats`) rather than wiring N adapters.
- **Negative / trade-off:** the schemas live in two places. The
  generated per-domain schemas at `packages/shared-schema/schemas/` are
  derived from Pydantic models via `make schemas`. The hand-authored
  wire schemas at `packages/shared-schema/*.schema.json` are the
  contract. We accept the duplication because the wire schemas have
  fields the in-memory models don't carry (e.g. `artifact_paths`,
  `summary`).
- **Negative / trade-off:** the redaction layer's depth limit (default 6) is shallower than SARIF needs. The SARIF writer bumps the depth
  to 12 via the new `ArtifactDirectory.write_json(..., redaction_depth=12)`
  parameter. Bumping further would defeat the depth guard against
  pathological structures; 12 was chosen because SARIF nests at most
  ~10 deep in practice.
- **Follow-up obligations:**
  - Phase 13 (Security module) and other module phases register their
    SARIF rules via `SarifRuleRegistry.register(...)`. Synthetic
    `GEN-*` rules from Phase 03 should rarely fire afterwards.
  - Phase 14 (Quality scoring) populates `ctx.typed_score` and
    `ctx.typed_policy`; the dispatcher's hook will then write real
    `score.json` with non-default policy values.
  - Phase 15 (Reports UI) builds the HTML template on top of these
    same JSON artifacts and replaces the Phase-03 Markdown writer with
    a richer renderer.
  - Phase 17 (CI integration) wires the SARIF artifact into
    `github/codeql-action/upload-sarif`.
  - Phase 24 (Plugin architecture) replaces the `Reporter`'s
    `if/elif` dispatch with entry-point discovery, honoring the
    existing `ReporterPlugin` Protocol.

## Alternatives considered

- **Generate wire schemas from Pydantic too.** Rejected: the wire format
  needs fields (`artifact_paths`, `summary`, `errors`) the in-memory
  domain doesn't carry, and trying to bolt them onto the Pydantic
  models conflates "in-memory shape" with "wire shape". Two schemas,
  each owning one concern, is clearer.
- **Skip the official SARIF schema and write a permissive subset.**
  Rejected: the whole point of SARIF is downstream tool interop; if our
  outputs don't validate against the official OASIS schema, the value
  proposition collapses. Vendoring 3 389 lines is cheaper than the
  alternative.
- **Have each writer manage its own redaction.** Rejected: redaction
  must be enforced at exactly one chokepoint. Letting each writer
  call `redact()` individually risks one writer forgetting. The
  `ArtifactDirectory.write_json`/`write_text` chokepoint is the
  single seam.
- **Always write every format, ignore `config.report.formats`.**
  Rejected: PRD §17.1 already exposes `report.formats` for a reason
  (some users want JUnit only; CI builds may not want SARIF). The
  dispatcher honors the config but still emits `run.json`
  unconditionally because that's the lifecycle record, not a
  "report".

## References

- PRD section(s): PRD §17 (Configuration), §18 (Data model), §19
  (Quality scoring), §20 (Evidence & reporting), §21 (CI), §24
  (Finding schema).
- CLAUDE.md rule(s): CLAUDE.md §11 (Artifact rules), §16 (Testing),
  §17 (Quality gates), §24 (Findings rules), §25 (Quality score
  rules), §32 (Error handling), §33 (Logging & secrets), §38
  (Report rules).
- External:
  - SARIF 2.1.0 OASIS spec —
    https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
  - JUnit XML / Surefire reporting —
    https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd
- Related ADRs: ADR-0005 (Config schema), ADR-0006 (Safety policy),
  ADR-0007 (Run lifecycle).
