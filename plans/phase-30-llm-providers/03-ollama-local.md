# Task 30.03 — Ollama (local) adapter

## Deliverables

- `engine/llm/providers/ollama.py` — `OllamaProvider`. Talks to a locally
  running Ollama server at `http://localhost:11434/api/chat` via `httpx`.
- No API key. The adapter assumes the user has already pulled the model
  (`ollama pull <name>`); `doctor()` lists installed models via
  `/api/tags` and reports unavailable if the requested model is missing.
- Structured output: Ollama 0.5+ supports a `format: <jsonschema>` field.
  The adapter passes the request's `response_schema` through verbatim,
  then re-validates client-side.
- Cost is always `0.0` (local compute); usage tokens come from the
  `eval_count` + `prompt_eval_count` fields.
- The adapter MUST NOT crash the run when the Ollama server is offline —
  it returns a `LlmResponse` with `available=False` and the caller falls
  back to the deterministic path (planner's `NullLlmPlanner`, analyzer's
  null explainer).
- Default model: `qwen2.5-coder:7b` (low-resource, structured-output
  capable). Override via `planner.llm.model`.

## Tests required

- `tests/unit/llm/providers/test_ollama.py` — mocked happy path,
  unreachable-server path, missing-model path, response-validation path.
- `tests/integration/llm/test_ollama_doctor.py` — when `OLLAMA_HOST` is
  unset or unreachable, `doctor()` returns `unavailable` cleanly; gated
  smoke test (`SENTINELQA_HAS_OLLAMA=1`) actually hits a live server.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] `OllamaProvider` is the documented "offline default" in
      `docs/dev/llm-providers.md`.
- [ ] `STATUS.md` updated.
