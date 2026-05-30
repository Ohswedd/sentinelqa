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
  TTL minus a 60s safety margin. JWT signing uses the PyCA
  [`cryptography`](https://pypi.org/project/cryptography/) library
  (added as a NEW direct dependency in `engine/pyproject.toml` for this
  task — it is not, contrary to the original draft of this task file, a
  transitive dep of `httpx`). The dependency is justified under
  CLAUDE.md §35: it is necessary (RS256 JWT signing without the
  `google-auth` SDK is not feasible without a real crypto library), it
  is the canonical Python crypto library (maintained by PyCA, BSD/Apache
  dual-licensed, audited), it has a small attack surface relative to a
  full Google SDK, and it replaces the much larger `google-auth` +
  `google-cloud-aiplatform` stack we are explicitly avoiding.
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
