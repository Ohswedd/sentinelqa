# sample-app-llm-broken

A deliberately-defective sample app for testing
:class:`modules.llm_audit.LlmAuditModule` . Each HTML file
illustrates one or more of the failure modes the LLM-Code audit module
hunts for. The JSON fixtures under
`tests/fixtures/llm_audit_broken/` capture the same defects in the
signal shape the module consumes so the integration suite stays
hermetic (no browser needed).

Defects illustrated:

| File             | Defect(s)                                           |
| ---------------- | --------------------------------------------------- |
| `index.html`     | Dead Save button + `coming soon` placeholder text   |
| `dashboard.html` | Mock user list ("John Doe") + console error ignored |
| `signup.html`    | Form without an `onsubmit` handler                  |
| `admin.html`     | UI hides admin link but backend serves 200          |
| `checkout.html`  | Missing loading state + `coming soon` in a P0 flow  |

This fixture is **not** intended to be served in production. Treat it
as a parallel to `sample-app-broken/`: a canonical defect catalogue
the audit module can detect.
