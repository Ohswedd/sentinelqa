# Task 30.01 — `engine.llm.LlmProvider` canonical Protocol

## Deliverables

- `engine/llm/__init__.py` exports the canonical surface: `LlmProvider`
  (`@runtime_checkable` Protocol), `LlmRequest`, `LlmResponse`,
  `LlmRedactionPolicy`, `LlmBudget`, `LlmRateLimit`, `NullLlmProvider`,
  `register_provider`, `resolve_provider`.
- `engine/llm/protocol.py` defines the Protocol:
  ```python
  class LlmProvider(Protocol):
      name: ClassVar[str]
      version: ClassVar[str]
      def complete(self, request: LlmRequest) -> LlmResponse: ...
      def doctor(self) -> ProviderHealth: ...
  ```
- `LlmRequest` carries `system`, `messages`, `response_schema`,
  `max_output_tokens`, `temperature`, `caller` (planner/analyzer/healer
  for cost attribution), `run_id` (for audit).
- `LlmResponse` carries `text`, `parsed` (typed via the request's
  `response_schema`), `usage` (tokens in/out), `cost_usd`, `latency_ms`,
  `provider`, `model`.
- `engine/llm/budget.py` — shared per-run cost cap (`LlmBudget`).
  Defaults from `pyproject` (existing planner/analyzer LLM block limits),
  enforced at call time, raises `BudgetExceededError`.
- `engine/llm/redaction.py` — every outgoing request body and incoming
  response body is run through `engine.policy.redaction.redact` before
  logging. Locked prompts live in their existing per-caller `*_prompts/`
  trees (Phase 06/09); the LlmProvider does NOT inline prompt text.
- The existing `engine.planner.llm_planner.LlmPlanner` and
  `engine.analyzer.llm_explainer.LlmExplainer` Protocols become thin
  facades that re-export from `engine.llm.*` (backwards-compat).
- New error codes in `engine/errors/codes.py`: `E-LLM-001..E-LLM-009`
  (missing key, model unavailable, budget exceeded, request rejected by
  provider, response validation failed, timeout, rate-limited,
  schema-mismatch, structured-output not supported).

## Tests required

- `tests/unit/llm/test_protocol_shape.py` — Protocol runtime check, IDs.
- `tests/unit/llm/test_budget.py` — `LlmBudget` enforcement; pre-call
  estimate vs post-call actual.
- `tests/unit/llm/test_redaction.py` — outgoing prompts + incoming
  responses both pass through `redact()`.
- `tests/integration/llm/test_provider_registry.py` — registering /
  resolving providers; conflict on duplicate registration.

## Definition of Done

- [ ] Protocol + helpers committed.
- [ ] All nine consumer call-sites (planner/analyzer/healer) compile
      against the new surface; existing functionality unchanged.
- [ ] Tests green.
- [ ] `STATUS.md` updated.
