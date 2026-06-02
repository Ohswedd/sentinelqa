# Mutation testing

Mutation testing checks the **quality of the test suite**, not the
correctness of the code under test. The runner makes small, mechanical
edits ("mutants") to the source — flipping a comparison, removing a
return, deleting a clause — and re-runs the suite. A mutant that
_survives_ (no test fails) is a hole in the suite: a code path the
tests don't actually exercise.

SentinelQA runs mutation testing against the paths that decide release
outcomes:

| Path                            | Why                                                  |
| ------------------------------- | ---------------------------------------------------- |
| `engine/scoring/`               | The whole scoring chain — score, blockers, decision. |
| `engine/scoring/policy_gate.py` | Orchestrator-facing wrapper.                         |
| `engine/policy/safety.py`       | The safety boundary itself.                          |
| `engine/policy/exit_codes.py`   | Exit-code mapping (drives CI gating).                |

The list lives in `pyproject.toml` under `[tool.mutmut]`.

## Running it

```bash
make mutation
```

This runs `mutmut run` (which generates and tests mutants in
`.mutmut-cache/`) followed by `mutmut results` (a summary table). To
inspect specific mutants:

```bash
make mutation-show          # show all
uv run mutmut show <id>     # show one
```

Wall-clock for the full run is on the order of several minutes (the
suite is fast; the mutant count is the cost driver). Mutation testing
is **not part of CI** — it's a periodic, on-demand check.

## The non-negotiable invariant

The safety boundary is the place where a surviving mutant translates
directly to a security incident. The single mutant we care about
above all others is:

> `SafetyPolicy.enforce()` mutated to _always return allowed_

If that mutation survives, an attacker who can influence target
configuration can drive destructive scans against unauthorized hosts.
The companion test module
`tests/unit/policy/test_safety_mutation_guards.py` documents the
specific invariants any mutation of `enforce` must break.

## Triaging surviving mutants

A surviving mutant is one of:

1. **A real test gap** — add a test that fails on the mutant. Default
   assumption.
2. **An equivalent mutation** — the mutated code is semantically
   identical to the original (e.g. flipping `>` to `>=` on a boundary
   that never hits equality). Annotate in the triage log; don't
   silence by weakening tests.
3. **A useless code path** — the mutated line had no observable effect
   because the surrounding code already shadows it. Delete the dead
   line; don't add a test that pins behaviour we don't want.

When in doubt, prefer adding a test. The cost of an extra assertion is
trivial; the cost of a missed regression in scoring or safety is not.
