# ADR-0006: Safety policy and target allowlist

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

SentinelQA's reputation rides on a single property: it cannot be turned into an attack tool. our product spec forbids stealth, evasion, bot-detection bypass, CAPTCHA bypass, fingerprint spoofing, proxy rotation for evasion, rate-limit bypass, unauthorized vulnerability exploitation, credential stuffing, and "undetectable" framing. our engineering rules: no destructive defaults, no public-target scans without explicit allow-listing, audit logs for every safety decision.

Every later module — discovery, security, performance, chaos, LLM-audit — must call into the same enforcement choke point, or the boundary will erode case by case. We also need a credible audit trail so a reviewer (legal, infosec, the user themselves) can reconstruct exactly what SentinelQA refused to do.

## Decision

`engine/policy/safety.py` exposes a stateless `SafetyPolicy` with a single public entry point — `enforce(target, requested_mode, *, audit_log_path=None, now=None) -> SafetyDecision`. Every module that touches a target MUST call this before any I/O.

The decision branches are explicit and finite:

1. **Local target + `safe` mode.** Allowed. (Loopback IPv4, IPv6 `::1`, RFC1918, link-local, and the literal names `localhost` / `ip6-localhost` / `ip6-loopback`.)
2. **Local target + `authorized_destructive` mode.** Allowed _only_ with a valid proof-of-authorization. Local destructive tests can wipe a dev database; a paper trail is mandatory.
3. **Public target + `safe` mode + host in `target.allowed_hosts`.** Allowed.
4. **Public target + `safe` mode + host NOT in allowlist.** Refused with `UnknownHostError` (E-SAFE-001, exit code 4).
5. **Public target + `authorized_destructive` + valid proof.** Allowed.
6. **Public target + `authorized_destructive` without proof / with expired proof / with wrong-host proof.** Refused with `DestructiveWithoutProofError` (E-SAFE-002).

Supporting decisions:

- **Forbidden capabilities.** `engine/policy/forbidden_features.py` holds the canonical deny-lists. Plugins/modules that attempt to register a forbidden capability or CLI flag fail with `ForbiddenFlagError` (E-SAFE-003) at registration time, before any user can invoke them. A `tests/security/test_no_stealth_flags.py` test sweeps the source tree for stealth-flag literals; the only allowed locations are the deny-list file, the test itself, and the policy docs.
- **Proof-of-authorization.** `engine/policy/proof_of_authorization.py` defines a small YAML schema (host, actor, scope, issued_at, expires_at, optional notes), validates with Pydantic, and verifies `host`, `capability ∈ scope`, and time bounds. release accepts unsigned docs; a follow-up ADR may add detached signing.
- **Audit log.** `engine/policy/audit_log.py` appends one redacted JSON line per decision (allowed or refused) to `.sentinel/runs/<run-id>/audit.log`. Redaction goes through `engine.policy.redaction.redact` before any bytes touch disk. owns the run directory; the audit module is safe to call with a not-yet-existing path (parent dirs are created on first write).
- **No silent allow.** The `requires_proof_of_authorization` helper is a positive answer to "does this combo need proof?"; the negative path is constrained to local+safe and allowlisted+safe explicitly.

Forbidden by construction (NOT just by convention):

- Any "stealth" or "evasion" CLI flag — caught by the deny-list scan and the registry.
- Wildcard allow-lists — Pydantic validator on `Target.allowed_hosts` and `TargetConfig.allowed_hosts` rejects `*` and `?`.
- Destructive defaults — `security.mode` defaults to `"safe"`; `destructive_tests` defaults to `false`; the `authorized_destructive` mode requires a proof file.

## Consequences

- **Positive.** Single choke point for every later module. The gate review asserts that an unallowlisted host raises `UnknownHostError` and the CLI smoke test maps it to exit code 4 — locking this contract before any networked module ships.
- **Positive.** The audit log is the receipts the legal/infosec reviewer needs. JSONL means it's grep-able and diff-able.
- **Positive.** The deny-list lives next to the test that scans the tree for it. Re-introducing a stealth flag in a future PR fails CI immediately.
- **Negative / trade-off.** Proof-of-authorization is unsigned in release. That's lighter than ideal — a malicious actor with write access to the repo could fabricate one. We accept this trade-off because (a) the alternative is asymmetric signing that we're not ready to wire in, and (b) the proof file's value is the audit trail it leaves, not unforgeable consent.
- **Negative / trade-off.** Refusing local destructive without a proof is stricter than our engineering rules; if it turns out to be too tight for a real dev workflow, a future ADR can scope it down.
- **Follow-up obligations.** (Security module) must enforce per-payload-level gates on top of `SafetyPolicy.enforce`. (Plugin architecture) must wire `assert_capability_allowed` into the plugin loader.

## Alternatives considered

- **One safety decision per module, configured by per-module YAML.** Rejected. Inevitable drift; reviewers can't audit a forest of decision points.
- **Block all non-local targets unconditionally.** Rejected. The product needs to work against authorized staging hosts (which the user owns); an explicit allow-list with proof requirements for destructive ops is the right point on the curve.
- **Signed proof-of-authorization out of the gate.** Deferred. Adds a key-management dependency we're not ready to spec in.
- **Rely on rate-limiting alone for safety.** Rejected. Rate limits prevent abuse against allow-listed targets; they don't prevent contacting a non-allow-listed target in the first place.

## References

- PRD section(s): our product spec (Safety & Legal Boundary), our product spec (Threat Model), our product spec (Security Module rules), our product spec (Data Model — Target).
- our engineering rules rule(s): our engineering rules(Safety boundary), our engineering rules(Security module rules), our engineering rules(Error handling — typed errors with codes), our engineering rules(Required ADR triggers — "Security policy").
- External: OWASP Web Security Testing Guide (authorization-scoped DAST principles).
- Related ADRs: ADR-0005 (Config schema — owns `target.proof_of_authorization` field), ADR-0001 (Repository structure — `engine/policy/` location).
