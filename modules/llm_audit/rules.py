"""Stable ``LLM-*`` rule catalogue for the LLM-Code audit module.

Each rule pins a deterministic ID, a default severity, a default
confidence, and a curated remediation. Rules are referenced by the
per-check modules under :mod:`modules.llm_audit.checks` and surfaced
in our product spec evidence so downstream consumers (Reporter, SDK) render the
same wording.

Bumps to a rule's wording or default severity require an ADR-0024
amendment per our engineering rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.domain.finding import Severity


@dataclass(frozen=True)
class LlmAuditRule:
    """A single LLM-* rule.

    ``severity`` and ``confidence`` are *defaults*; concrete checks can
    override them when a specific signal warrants it (e.g. a "coming
    soon" string on a P0 flow gets bumped to high, see
    ``modules.llm_audit.checks.coming_soon``).
    """

    id: str
    category: str
    title: str
    severity: Severity
    confidence: float
    remediation: str


# ---------------------------------------------------------------------------
# Catalogue (stable IDs — referenced by SARIF + Reporter)
# ---------------------------------------------------------------------------


LLM_DEAD_BTN = LlmAuditRule(
    id="LLM-DEAD-BTN",
    category="llm_audit_dead_button",
    title="Button has no observed handler",
    severity="high",
    confidence=0.8,
    remediation=(
        "Wire the button to an `onClick` handler that performs the "
        "advertised action — submit a request, update local state, or "
        "navigate. If the button is intentionally decorative, mark it "
        "with `aria-disabled='true'` and provide a non-button element."
    ),
)

LLM_FAKE_ROUTE = LlmAuditRule(
    id="LLM-FAKE-ROUTE",
    category="llm_audit_fake_route",
    title="Internal link points at a route the app does not serve",
    severity="high",
    confidence=0.85,
    remediation=(
        "Either implement the missing route or remove the link. "
        "Generated apps often leave navigation entries for unfinished "
        "screens — silent 404s erode user trust quickly."
    ),
)

LLM_FAKE_ENDPOINT = LlmAuditRule(
    id="LLM-FAKE-ENDPOINT",
    category="llm_audit_fake_endpoint",
    title="Frontend calls an API endpoint the backend does not expose",
    severity="high",
    confidence=0.75,
    remediation=(
        "Implement the endpoint server-side or remove the call. "
        "OpenAPI / GraphQL introspection should list every endpoint the "
        "frontend depends on so this regression is caught at build time."
    ),
)

LLM_MOCK_DATA_SHIPPED = LlmAuditRule(
    id="LLM-MOCK-DATA-SHIPPED",
    category="llm_audit_mock_data",
    title="Mock fixtures appear in the production bundle",
    severity="high",
    confidence=0.85,
    remediation=(
        "Move mock data behind a `process.env.NODE_ENV` guard and ensure "
        "the bundler tree-shakes it from production builds. Hardcoded "
        "user lists (e.g. 'John Doe', 'jane@example.com') frequently "
        "ship straight into prod from generated MVPs."
    ),
)

LLM_FORM_NO_SUBMIT = LlmAuditRule(
    id="LLM-FORM-NO-SUBMIT",
    category="llm_audit_form_no_submit",
    title="Form has no working submit path",
    severity="high",
    confidence=0.9,
    remediation=(
        "Attach an `onSubmit` handler that POSTs the form payload to a "
        "real endpoint and renders success / error UI based on the "
        "response. Forms without submit handlers are the single most "
        "common defect in LLM-generated apps."
    ),
)

LLM_INCOMPLETE_CRUD = LlmAuditRule(
    id="LLM-INCOMPLETE-CRUD",
    category="llm_audit_incomplete_crud",
    title="Resource exposes Create without Read / Update / Delete",
    severity="medium",
    confidence=0.7,
    remediation=(
        "Implement the missing edges — at minimum a list endpoint, a "
        "single-item GET, an update PATCH/PUT, and a DELETE. Partial "
        "CRUD ships when an LLM stops generating after the first "
        "happy-path scaffold."
    ),
)

LLM_UI_ONLY_AUTH = LlmAuditRule(
    id="LLM-UI-ONLY-AUTH",
    category="llm_audit_ui_only_auth",
    title="Backend serves UI-hidden route to an unauthorized user",
    severity="critical",
    confidence=0.9,
    remediation=(
        "Move authorization to the server. The UI can hide a link, but "
        "the backend MUST refuse the request based on the session's "
        "actual role. Cross-reference Phase 13's IDOR / role checks."
    ),
)

LLM_HARDCODED_CRED = LlmAuditRule(
    id="LLM-HARDCODED-CRED",
    category="llm_audit_hardcoded_cred",
    title="Hardcoded credential appears in shipped source",
    severity="high",
    confidence=0.85,
    remediation=(
        "Remove the credential from source and rotate it immediately. "
        "Credentials belong in environment variables or a secret store. "
        "If the value was intended as a demo placeholder, replace it "
        "with a clearly-fake string that cannot grant access."
    ),
)

LLM_CLIENT_SECRET_STORAGE = LlmAuditRule(
    id="LLM-CLIENT-SECRET-STORAGE",
    category="llm_audit_client_secret_storage",
    title="Browser storage contains a value that looks like a secret",
    severity="medium",
    confidence=0.75,
    remediation=(
        "Store auth state in HttpOnly + Secure cookies rather than "
        "localStorage / sessionStorage. XSS payloads read browser "
        "storage trivially; HttpOnly cookies are out of script reach."
    ),
)

LLM_NO_LOADING_STATE = LlmAuditRule(
    id="LLM-NO-LOADING-STATE",
    category="llm_audit_no_loading_state",
    title="Slow API call has no loading indicator",
    severity="medium",
    confidence=0.7,
    remediation=(
        "Render a skeleton, spinner, or other affordance when a "
        "pending request is in flight. Users assume an app froze when "
        "nothing changes after a click."
    ),
)

LLM_NO_ERROR_STATE = LlmAuditRule(
    id="LLM-NO-ERROR-STATE",
    category="llm_audit_no_error_state",
    title="Failed API call produces no error UI",
    severity="high",
    confidence=0.85,
    remediation=(
        "Render a user-visible error state when a request fails. "
        "Silent failures mask real outages and erode trust faster than "
        "any other LLM-generated defect."
    ),
)

LLM_VALIDATION_BACKEND_ACCEPTS = LlmAuditRule(
    id="LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS",
    category="llm_audit_validation_mismatch",
    title="Frontend rejects payload the backend accepts",
    severity="high",
    confidence=0.9,
    remediation=(
        "Move the validation rule to the server. Client-side checks are "
        "a UX optimization; the server is the only authoritative "
        "validator."
    ),
)

LLM_VALIDATION_FRONTEND_MISSING = LlmAuditRule(
    id="LLM-VALIDATION-MISMATCH-FRONTEND-MISSING",
    category="llm_audit_validation_mismatch",
    title="Backend rejects payload the frontend submitted as-is",
    severity="medium",
    confidence=0.85,
    remediation=(
        "Add the matching frontend validation so the user gets fast "
        "feedback. Re-confirm the rule server-side as the source of "
        "truth."
    ),
)

LLM_PLACEHOLDER_TEXT = LlmAuditRule(
    id="LLM-PLACEHOLDER-TEXT",
    category="llm_audit_placeholder_text",
    title="Placeholder text leaked into a user-facing flow",
    severity="low",
    confidence=0.95,
    remediation=(
        "Replace the placeholder with real copy or remove the screen "
        "from navigation until the feature is implemented. Strings like "
        "'coming soon', 'TBD', 'lorem ipsum', '{placeholder}' should "
        "never reach production."
    ),
)

LLM_CONSOLE_ERROR_IGNORED = LlmAuditRule(
    id="LLM-CONSOLE-ERROR-IGNORED",
    category="llm_audit_console_error",
    title="Console error surfaced while the UI reported success",
    severity="medium",
    confidence=0.8,
    remediation=(
        "Surface the underlying error to the user (toast, banner, "
        "inline message) or fix the failure outright. A green UI over a "
        "red console almost always corresponds to a silently broken "
        "feature."
    ),
)

LLM_UNHANDLED_PROMISE = LlmAuditRule(
    id="LLM-UNHANDLED-PROMISE",
    category="llm_audit_unhandled_promise",
    title="Unhandled promise rejection observed",
    severity="medium",
    confidence=0.85,
    remediation=(
        "Await the promise and wrap it in a try/catch, or attach an "
        "explicit `.catch()` handler. Unhandled rejections crash "
        "browser tabs on some engines and mask real errors elsewhere."
    ),
)


RULES: tuple[LlmAuditRule, ...] = (
    LLM_DEAD_BTN,
    LLM_FAKE_ROUTE,
    LLM_FAKE_ENDPOINT,
    LLM_MOCK_DATA_SHIPPED,
    LLM_FORM_NO_SUBMIT,
    LLM_INCOMPLETE_CRUD,
    LLM_UI_ONLY_AUTH,
    LLM_HARDCODED_CRED,
    LLM_CLIENT_SECRET_STORAGE,
    LLM_NO_LOADING_STATE,
    LLM_NO_ERROR_STATE,
    LLM_VALIDATION_BACKEND_ACCEPTS,
    LLM_VALIDATION_FRONTEND_MISSING,
    LLM_PLACEHOLDER_TEXT,
    LLM_CONSOLE_ERROR_IGNORED,
    LLM_UNHANDLED_PROMISE,
)


_BY_ID: dict[str, LlmAuditRule] = {rule.id: rule for rule in RULES}


def get_rule(rule_id: str) -> LlmAuditRule:
    """Look up a rule by ID. Raises ``KeyError`` if unknown."""

    return _BY_ID[rule_id]


__all__ = [
    "LlmAuditRule",
    "RULES",
    "get_rule",
    "LLM_DEAD_BTN",
    "LLM_FAKE_ROUTE",
    "LLM_FAKE_ENDPOINT",
    "LLM_MOCK_DATA_SHIPPED",
    "LLM_FORM_NO_SUBMIT",
    "LLM_INCOMPLETE_CRUD",
    "LLM_UI_ONLY_AUTH",
    "LLM_HARDCODED_CRED",
    "LLM_CLIENT_SECRET_STORAGE",
    "LLM_NO_LOADING_STATE",
    "LLM_NO_ERROR_STATE",
    "LLM_VALIDATION_BACKEND_ACCEPTS",
    "LLM_VALIDATION_FRONTEND_MISSING",
    "LLM_PLACEHOLDER_TEXT",
    "LLM_CONSOLE_ERROR_IGNORED",
    "LLM_UNHANDLED_PROMISE",
]
