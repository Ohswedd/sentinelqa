# Task 01.02 — Configuration schema & loader

## Objective

Implement strict loading and validation of `sentinel.config.yaml` (PRD §17). Enforce CLAUDE §12 config rules: safe defaults, explicit errors, no silent dangerous fallback, env interpolation, secret redaction, unknown-key rejection, CI-safe defaults.

## Prerequisites

- Task 01.01 complete (domain models exist).

## Deliverables

- `engine/config/schema.py` — Pydantic models matching the YAML structure in PRD §17.1, including:
  - `ProjectConfig`, `SourceConfig`, `TargetConfig`, `AuthConfig`, `ModulesConfig`, `SecurityConfig`, `PerformanceConfig`, `VisualConfig`, `PolicyConfig`, `ReportConfig`.
- `engine/config/loader.py` exposing `load_config(path: Path) -> RootConfig` that:
  - Reads YAML safely (`yaml.safe_load`).
  - Interpolates `${ENV_VAR}` placeholders (and `${ENV_VAR:-default}` form) — but only for non-secret fields. Secret fields must be passed by env var, never inlined.
  - Validates against the Pydantic models; rejects unknown keys.
  - Applies safe defaults per CLAUDE §12 (e.g. `security.mode = "safe"` if missing).
  - Returns a `RootConfig` object (frozen).
- `sentinel.config.yaml.example` at repo root — fully-populated example that round-trips.
- `engine/config/schema_check.py` exposing `validate_config_dict(d) -> list[ConfigError]` for the CLI `doctor` command (Phase 02) to call without raising.
- `engine/config/migration.py` placeholder with a stub for future schema-version migrations.
- ADR-0005: Config schema.

## Steps

1. Translate the example YAML in PRD §17.1 into Pydantic models. Make every field typed; use `Literal[...]` for enumerations (e.g. `mode: Literal["safe", "authorized_destructive"]`).
2. Add validators that reject:
   - `target.allowed_hosts` containing a wildcard.
   - `security.mode == "authorized_destructive"` without an explicit `target.proof_of_authorization`.
   - `policy.min_quality_score` outside 0–100.
   - `performance.budgets.*` with negative numbers.
3. Implement `${ENV}` interpolation with a small grammar (no shell, no exec). Forbid interpolation in keys.
4. Write `load_config()` to detect file-not-found, syntax errors, validation errors, and raise the typed exceptions from task 01.04.
5. Add a `dump_config()` for the `init` command (Phase 02) to write a default config.
6. Write the example file. Test that `load_config(example) ==  load_config(example)` (idempotent).

## Acceptance criteria

- The example YAML round-trips and produces a fully-typed `RootConfig`.
- Unknown keys cause `ConfigSchemaError`.
- Missing required keys produce a precise error message naming the field path.
- Env interpolation works for `target.base_url: ${BASE_URL}` but **does not** silently allow `auth.password: ${TEST_USER_PASSWORD}` to land in memory in clear text — that field is **not allowed inline** at all; auth uses `*_env` keys to name the env var.
- `make typecheck` passes; mypy strict.

## Tests required

- `tests/unit/config/test_schema.py` — every field path, every validator branch.
- `tests/unit/config/test_loader.py` — file-not-found, YAML syntax errors, unknown keys, default application, env interpolation.
- `tests/unit/config/test_secret_safety.py` — confirms passwords cannot be inlined.

## PRD / CLAUDE.md references

- PRD §17 Configuration Specification.
- CLAUDE.md §12 Config rules, §33 Logging & secrets.

## Definition of Done

- [ ] Schema models implemented and tested.
- [ ] Loader rejects every malformed example in tests.
- [ ] Example YAML committed at repo root.
- [ ] ADR-0005 committed.
- [ ] `STATUS.md` updated.
