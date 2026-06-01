# ADR-0005: Configuration schema

## Status

Accepted

<!-- Date: 2026-05-27 -->
<!-- Authors: @ohswedd -->

## Context

SentinelQA needs a single, strictly-validated configuration surface (`sentinel.config.yaml`) that the CLI, SDK, modules, and CI all read identically. our product spec sketches the YAML layout; our engineering rules(safe defaults, explicit errors, no silent dangerous fallback, env interpolation, secret redaction, unknown-key rejection, CI-safe behaviour without prompts).

Two failure modes are unacceptable:

1. Silent acceptance of an unknown key — that erodes the schema-version contract and lets typos masquerade as feature toggles.
2. Inline secrets — committing a config file with a real password or token is a data-loss event.

We need a representation that catches both at parse time and produces actionable error messages for the CLI to render.

## Decision

The canonical config schema lives in `engine/config/schema.py` as a tree of Pydantic v2 models rooted at `RootConfig`, with `model_config = ConfigDict(frozen=True, extra="forbid")` enforced via the `SentinelModel` base. The loader at `engine/config/loader.py` is the only public entry point; ad-hoc YAML parsing elsewhere in the codebase is forbidden.

Specific decisions:

- **YAML reading.** `yaml.safe_load`. Never `yaml.load`. This precludes the constructor-tag execution path that has produced RCE bugs in other tools.
- **Env interpolation.** Bare strings may contain `${VAR}` or `${VAR:-default}` placeholders. The grammar is regex-only; no shell expansion, no command substitution. Keys themselves are never interpolated. Unset variables with no default raise `ConfigSchemaError` (E-CFG-002).
- **Secret-name keys.** A small allow-list of secret-shaped keys (`password`, `secret`, `token`, `access_token`, `refresh_token`, `api_key`, `client_secret`, `private_key`) raises `ConfigSecretInlineError` (E-CFG-003) when a scalar value lands there. Authentication strategies must use the `*_env` sibling keys (`username_env`, `password_env`, `token_env`).
- **Wildcards forbidden.** `target.allowed_hosts` rejects any host containing `*` or `?`. The safety boundary in our engineering rules-list being explicit; a wildcard would make the policy lie.
- **Destructive mode requires proof.** A `RootConfig` model_validator refuses `security.mode == "authorized_destructive"` unless `target.proof_of_authorization` is set. The proof file itself is loaded and verified by `engine/policy/proof_of_authorization.py` at policy-enforcement time (ADR-0006).
- **Schema version.** `RootConfig` carries `CONFIG_SCHEMA_VERSION = "1"`. Migrations live in `engine/config/migration.py` and are empty in Phase 01.
- **Non-raising surface.** `engine/config/schema_check.py` exposes `validate_config_dict(dict) -> list[ConfigCheckError]` so `sentinel doctor` (Phase 02) can list every issue in one pass without raising.

The Phase 01 task spec lists `engine/config/schema.py`, `loader.py`, `schema_check.py`, and `migration.py`; this ADR makes the contract that backs them durable.

## Consequences

- **Positive.** One canonical schema. Tests, docs, and `sentinel doctor` all derive from the same Pydantic models — there is no second source of truth to drift. Unknown keys fail loudly; inline secrets fail loudly; wildcard allow-lists fail loudly.
- **Positive.** Env interpolation supports `${VAR:-default}`, which is the minimum DX needed for the CI/local-dev split without inventing a shell-like syntax.
- **Negative / trade-off.** `extra="forbid"` means each new module feature requires both a schema bump and a model field. That is the trade we want — features shouldn't sneak in via undocumented keys — but it does add friction for plugin authors. Phase 24 (plugin architecture) will introduce a typed extension mechanism so plugins don't fork the schema.
- **Negative / trade-off.** Pydantic's strict type checks make tests verbose (str-vs-AnyUrl mismatches surface as ValidationError rather than auto-coercion). We accept this; for tests, a per-package mypy override softens `arg-type` only.
- **Follow-up obligations.** When `CONFIG_SCHEMA_VERSION` ever bumps, the policy in `docs/dev/schema-versioning.md` must be followed and a migration must land in `engine/config/migration.py`.

## Alternatives considered

- **TOML or JSON.** Rejected. YAML is the existing PRD format and the ecosystem norm for QA tools; switching now would invalidate the PRD's example and offer no upside for the security boundary.
- **Pure dataclass + manual validation.** Rejected. We'd reinvent Pydantic v2's error reporting and JSON-Schema export poorly, then spend ongoing time keeping them aligned.
- **Allow inline secrets and rely on git hooks to catch them.** Rejected. Defense in depth: gitleaks (pre-commit) catches commits; the loader catches misuse of the file. Both. our engineering rules— which is impossible to guarantee if the config can carry them.
- **Auto-coerce strings to AnyUrl in tests via plugin.** Rejected. The cost of writing the URL once is lower than the cost of teaching reviewers to trust the magic.

## References

- PRD section(s): our product spec (Configuration Specification), our product spec (Data Model — Project / Target).
- our engineering rules rule(s): our engineering rules(Config rules), our engineering rules(Logging & secrets), our engineering rules(Safety boundary), our engineering rules(Required ADR triggers — "Config schema").
- External: Pydantic v2 strict mode docs; OWASP YAML parsing guidance (`yaml.safe_load`).
- Related ADRs: ADR-0002 (Language strategy — Python owns config), ADR-0003 (Package managers — uv workspace), ADR-0006 (Safety policy — consumer of `target.proof_of_authorization`).
