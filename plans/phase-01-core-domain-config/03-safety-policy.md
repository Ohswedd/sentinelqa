# Task 01.03 — Safety policy & target allowlist

## Objective

Implement the non-negotiable safety boundary (PRD §2 / CLAUDE §6, §26). Every later module must call `SafetyPolicy.enforce(target, requested_mode)` before any I/O against a target.

## Prerequisites

- Tasks 01.01 and 01.02 complete.

## Deliverables

- `engine/policy/safety.py` exposing:
  - `class SafetyPolicy` with methods:
    - `enforce(target: Target, requested_mode: Mode) -> SafetyDecision` — raises `UnsafeTargetError` if the target is not allowed for the requested mode.
    - `is_local(host: str) -> bool` — matches `localhost`, `127.0.0.1`, `::1`, and RFC1918 ranges.
    - `requires_proof_of_authorization(target, mode) -> bool` — true for any public host or any destructive mode.
  - `class SafetyDecision` (frozen) with `allowed: bool`, `reason: str`, `target: Target`, `mode: Mode`, `evidence: list[str]`.
- `engine/policy/forbidden_features.py` — a module-scope frozenset listing the **forbidden capability strings** from CLAUDE §6 (`bot_detection_bypass`, `captcha_bypass`, `stealth_automation`, `fingerprint_evasion`, `credential_stuffing`, `proxy_rotation_for_evasion`, `rate_limit_bypass`, etc.). Any module attempting to register a capability in this list at runtime must fail loudly. Phase 24 (plugins) will consult it.
- `engine/policy/audit_log.py` — appends safety decisions to the run artifact `.sentinel/runs/<run-id>/audit.log` (created in Phase 02).
- `engine/policy/proof_of_authorization.py` — schema and verifier for a `proof_of_authorization` doc (path to a file under the project root, signed or unsigned for MVP, containing target host, authorized actor, scope, expiry).
- ADR-0006: Safety policy.

## Steps

1. Implement `SafetyPolicy` with explicit branches:
   - Local target + `safe` mode → allowed.
   - Local target + `authorized_destructive` mode → allowed, but logged.
   - Public target + `safe` mode + host in `allowed_hosts` → allowed.
   - Public target + `safe` mode + host NOT in allowlist → `UnsafeTargetError`.
   - Public target + `authorized_destructive` → requires valid proof-of-authorization file.
2. Implement IPv4/IPv6 + hostname parsing using `ipaddress` and `urllib.parse`. Handle ports.
3. Wire `audit_log` to write a JSON Line per decision, with redaction applied.
4. Implement the proof-of-authorization verifier (presence, schema, host match, not-expired).
5. Add a CLI exit-code mapping reference in `engine/policy/exit_codes.py` (used by Phase 02): `UNSAFE_TARGET = 4` per PRD §13.2 / CLAUDE §13.

## Acceptance criteria

- Trying to audit `https://google.com` without an allowlist entry raises `UnsafeTargetError` with a precise reason.
- Trying to run destructive security checks against an allowlisted host without proof-of-authorization is rejected.
- Audit log entries are JSON Lines, contain a UTC timestamp, decision, target host, mode, reason, and **never** contain secrets.

## Tests required

- `tests/unit/policy/test_safety_policy.py` — every decision branch.
- `tests/unit/policy/test_forbidden_features.py` — registering a forbidden capability fails.
- `tests/unit/policy/test_audit_log.py` — log lines are valid JSON, redacted.
- `tests/security/test_no_stealth_flags.py` — the CLI (when added in Phase 02) must not accept any `--stealth` / `--evade` / `--bypass-*` flag; this test scans the argument parsers.

## PRD / CLAUDE.md references

- PRD §2 Safety & Legal Boundary, §23 Threat Model, §26 Security Module rules.
- CLAUDE.md §6 Safety boundary, §26 Security module rules.

## Definition of Done

- [ ] `SafetyPolicy.enforce()` covers every PRD §2 / CLAUDE §6 case.
- [ ] Forbidden-features list complete.
- [ ] Audit log writes redacted JSONL.
- [ ] Proof-of-authorization schema + verifier in place.
- [ ] ADR-0006 committed.
- [ ] `STATUS.md` updated.
