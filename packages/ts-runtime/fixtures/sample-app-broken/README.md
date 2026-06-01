# Sample app — broken variant (Phase 10.05)

This sibling of `sample-app/` deliberately ships defects so the functional
module's failure path can be exercised end-to-end:

- The login form action points at a page that never marks the user signed in (the "success" page has no signed-in marker), so any test asserting a post-login anchor must fail.
- The hint paragraph claims "Use any email to continue." but the form's submit handler is missing (no JS), so a real test against the rendered outcome surfaces the inconsistency Phase 19 flags.
- A second route (`/admin`) returns the public landing instead of a guarded page, so role-boundary tests should report a missing 403/redirect.

The fixture is **only** used by SentinelQA's own integration test suite
(`tests/integration/modules/functional/test_runner_sweep.py`) — never
distribute it as an example app.
