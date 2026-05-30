# Task 30.10 — `sentinel llm` CLI surface + config polish

## Deliverables

- New Typer subapp `sentinel llm` registered under `sentinel_cli.app`:
  - `sentinel llm list` — prints the registered providers (name, version,
    available models, whether the credential env var is set). JSON mode
    supported.
  - `sentinel llm doctor [--provider <name>]` — runs each registered
    provider's `doctor()`, prints reachability + latency + budget
    estimate. JSON mode supported. Exit code grid: 0 (all reachable),
    1 (one or more unreachable but the user has configured one that IS
    reachable), 5 (no provider reachable AND a provider is required by
    config).
  - `sentinel llm price --provider <name> --model <model>` — prints the
    cost table for that provider's model.
- Config schema additions in `engine/config/schema.py`:
  ```yaml
  llm:
    default_provider: anthropic        # one of the nine registered names
    providers:
      anthropic:
        api_key_env: ANTHROPIC_API_KEY
        models: { planner: claude-3-5-sonnet, analyzer: claude-3-5-haiku }
      gemini: { api_key_env: GEMINI_API_KEY, ... }
      ollama: { host: http://localhost:11434, models: { planner: qwen2.5-coder:7b } }
      ...
  ```
- The existing `planner.llm.*` and `analyzer.llm.*` blocks gain a
  `provider:` field; when set, it overrides `llm.default_provider` for
  that consumer.
- `apps/cli/src/sentinel_cli/commands/llm_cmd.py` — the subapp module.
- `docs/dev/llm-providers.md` — per-provider config table; setup steps;
  cost ballparks; "which provider should I pick?" guide.

## Tests required

- `tests/integration/cli/test_llm_command.py` — list / doctor / price;
  every exit-code branch.
- `tests/unit/config/test_llm_block.py` — strict validation; rejects
  unknown providers; rejects missing-key env var name; default
  inheritance.

## Definition of Done

- [ ] `sentinel llm doctor` ships and is documented.
- [ ] PRD §17.1 documents the new `llm:` config block.
- [ ] `STATUS.md` updated.
