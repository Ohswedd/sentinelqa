# Task 30.05 — Google Vertex AI adapter

## Deliverables

- `engine/llm/providers/vertex.py` — `VertexAiProvider`. Calls Vertex AI's
  REST endpoint at
  `https://<region>-aiplatform.googleapis.com/v1/projects/<project>/locations/<region>/publishers/google/models/<model>:generateContent`
  via `httpx`. No `google-cloud-aiplatform` SDK.
- Auth: Google service-account JSON key file referenced by
  `GOOGLE_APPLICATION_CREDENTIALS`. The adapter exchanges the JWT for an
  access token via the OAuth2 token endpoint
  (`https://oauth2.googleapis.com/token`) and caches it for the token's
  TTL minus a 60s safety margin. JWT signing uses the stdlib
  `cryptography` package (already a transitive dep via `httpx`'s
  `cryptography` extras; pin explicitly).
- Same Gemini-family API shape as Phase 30.02; reuse the `gemini.py`
  payload builder.
- Cost mapping mirrors the Gemini provider but the rates come from
  Vertex's pricing surface.
- `doctor()` decodes the credentials file, verifies the JWT, and reports
  the project + region.

## Tests required

- `tests/unit/llm/providers/test_vertex.py` — mocked OAuth flow, JWT
  signing (hard-coded service-account fixture, public-key in test
  resources), happy path, expired-token refresh, missing-credentials
  path.

## Definition of Done

- [ ] Adapter green under mocks.
- [ ] `google-cloud-aiplatform`, `google-auth` not in `pyproject.toml`.
- [ ] `STATUS.md` updated.
