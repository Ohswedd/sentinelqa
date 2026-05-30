# Task 32.04 — GraphQL safety probe

## Deliverables

- `modules/security/checks/graphql_safety.py`. Activates when the
  Phase 05 discovery module detected one or more GraphQL endpoints
  (`api.json` carries `graphql: true` for the endpoint).
- Probes:
  1. Send the canonical introspection query
     (`{ __schema { types { name } } }`). If the production server
     responds with the schema, finding: `graphql-introspection-enabled`
     (CWE-200; `severity: high`).
  2. Send a depth-5 nested query (well-known recursion pattern using
     existing schema types — re-uses the introspected schema if
     available, else uses a generic `query { a(a:1) { b(b:1) { c { ...
     } } } }` shape). If the server accepts it, finding:
     `graphql-no-depth-limit` (CWE-770; `severity: medium`).
  3. Send a query containing five aliases for the same field
     (canonical complexity-attack shape). If the server doesn't
     reject, finding: `graphql-no-complexity-limit` (CWE-770;
     `severity: medium`).
  4. Walk the introspected schema for mutations. For each mutation,
     issue an anonymous request (no auth). If any returns a
     non-error response, finding: `graphql-mutation-no-auth`
     (CWE-862; `severity: high`).
- All four probes respect `target.rate_limit_rps` (Phase 05 token
  bucket); none are aggressive fuzzing.

## Tests required

- `tests/unit/modules/security/test_graphql_probe.py` — every probe's
  request shape; happy + bad fixtures.
- `tests/integration/modules/security/test_graphql_e2e.py` — driven
  against a `pytest-httpserver` GraphQL stub.

## Definition of Done

- [ ] Four probes ship with findings + CWEs.
- [ ] No probe enumerates more than the four canonical attack-shape
      cases (`tests/security/test_graphql_bounded.py` greps for any
      loop / random-mutation generator).
- [ ] `STATUS.md` updated.
