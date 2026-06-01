"""Root-cause hypothesis generation (the documentation, ).

For each ``FailureClassification`` we produce a 1-2 sentence hypothesis
plus an ordered ``next_actions`` checklist. Templates are intentionally
modest in confidence — the analyzer should under-claim ("Likely cause:
…") rather than overstate ("This is definitely…"). The Healer
gates its own auto-repair on the analyzer's confidence, so this layer
must NOT inflate it.

Templates avoid blame language and never assume a particular author.
"""

from __future__ import annotations

from typing import Final

from engine.analyzer.models import (
    FailureCategory,
    FailureClassification,
    FailureSignal,
    RootCauseHypothesis,
)

# Per-category default hypothesis + actions. The first ``{}`` placeholder
# is substituted with a short, evidence-derived snippet (e.g. the failing
# URL, the locator name, the response code).
_TEMPLATES: Final[dict[FailureCategory, tuple[str, tuple[str, ...]]]] = {
    "app_bug": (
        "The server returned an error ({0}) while the test was exercising the app. "
        "Likely cause: a server-side defect or broken downstream dependency.",
        (
            "Open the trace zip and inspect the failing network request.",
            "Check server logs around the timestamp of the failing request.",
            "Reproduce manually against the same target to confirm the 5xx.",
        ),
    ),
    "test_bug": (
        "The test could not interact with element {0} within the timeout while the app "
        "appeared healthy. Likely cause: the locator is stale, the element is "
        "conditionally rendered, or the wait condition is wrong.",
        (
            "Open the failing step in the trace viewer to see the DOM snapshot.",
            "Confirm the element name / role used by the locator still matches the UI.",
            "Consider a more semantic locator (getByRole / getByLabel).",
        ),
    ),
    "environment_failure": (
        "The test runtime itself failed: {0}. Likely cause: browser crash, host "
        "outage, port conflict, or missing dependency — not an application bug.",
        (
            "Re-run the test in isolation to confirm reproducibility.",
            "Check disk space, available memory, and any host-level constraints.",
            "Verify the target host responds to a plain curl from the runner host.",
        ),
    ),
    "flake": (
        "The test passed on a later attempt after failing earlier. {0} The failure is "
        "non-deterministic; treat as a flake until a stable repro exists.",
        (
            "Inspect the failing-attempt trace for race conditions or animation timing.",
            "If recurring, add the test to the quarantine list with an issue.",
            "Avoid hard-coded waits — prefer Playwright auto-waiting.",
        ),
    ),
    "data_setup_failure": (
        "Test data / fixture setup failed before the test body executed. {0} "
        "Likely cause: a seed step raised, or a required fixture is missing.",
        (
            "Re-run the fixture in isolation to confirm the failure point.",
            "Check the data layer is reachable and the seed inputs are valid.",
            "Confirm the fixture is gated correctly for the configured security.mode.",
        ),
    ),
    "auth_failure": (
        "Authentication failed during the run: {0}. Likely cause: credentials "
        "rotated, login flow changed, or the configured ``*_env`` value is empty.",
        (
            "Verify the configured env-var name is set in this environment.",
            "Open the login step trace to see the response and any redirects.",
            "Confirm the login URL and selectors still match the current UI.",
        ),
    ),
    "api_failure": (
        "An API call returned {0} during the test. Likely cause: contract drift, "
        "stale fixture data, or a missing required header.",
        (
            "Inspect the request / response payload in the HAR file.",
            "Compare the request shape against the OpenAPI / GraphQL schema.",
            "Verify auth headers are present and not redacted to empty strings.",
        ),
    ),
    "performance_regression": (
        "A performance budget was exceeded: {0}. Likely cause: a recent deploy "
        "introduced a slow path or larger payload.",
        (
            "Inspect the WebPageTest / Lighthouse style metrics in the report.",
            "Diff bundle sizes against the prior run if history exists.",
            "Re-run with a clean profile to rule out warm-cache skew.",
        ),
    ),
    "security_finding": (
        "A safe-by-default security check fired: {0}. Likely cause: missing or "
        "misconfigured security header / cookie attribute.",
        (
            "Read the finding's recommendation for the precise header to set.",
            "Patch the application and re-run the security module in isolation.",
            "Do NOT weaken or skip the assertion — see the engineering guidelines.",
        ),
    ),
    "accessibility_violation": (
        "An accessibility assertion fired: {0}. Likely cause: missing label, "
        "insufficient contrast, or an ARIA misuse.",
        (
            "Open the linked rule in the axe-core ruleset documentation.",
            "Fix the underlying markup; do not weaken the assertion.",
            "Re-run the a11y module to confirm the violation count dropped.",
        ),
    ),
    "unknown": (
        "The failure pattern does not match any known rule: {0}. The most useful "
        "next step is to open the trace and review the failing step in context.",
        (
            "Open the trace zip in Playwright trace viewer.",
            "Read the error message and stack trace verbatim.",
            "If a clear pattern emerges, file a feature request to add a rule.",
        ),
    ),
}


def hypothesize(
    signal: FailureSignal,
    classification: FailureClassification,
) -> RootCauseHypothesis:
    """Return the deterministic root-cause :class:`RootCauseHypothesis`."""

    template, actions = _TEMPLATES[classification.category]
    snippet = _evidence_snippet(signal, classification.category)
    text = template.format(snippet)
    if len(text) > 1024:
        text = text[:1021] + "..."
    return RootCauseHypothesis(
        category=classification.category,
        hypothesis=text,
        confidence=classification.confidence,
        evidence_refs=_collect_evidence_refs(signal),
        next_actions=actions,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _evidence_snippet(signal: FailureSignal, category: FailureCategory) -> str:
    """Return a short, redaction-safe snippet to interpolate into the template.

    Keeps URLs / locator names short and falls back to a neutral
    description so the hypothesis remains grammatical even when the
    raw evidence is missing.
    """

    if category == "app_bug":
        bad = next(
            (n for n in signal.network if 500 <= n.status_code < 600),
            None,
        )
        if bad is not None:
            return f"HTTP {bad.status_code} from {_short_url(bad.url)}"
        return "an unexpected server response"
    if category == "test_bug":
        return _locator_snippet(signal)
    if category == "environment_failure":
        if signal.error_name and signal.error_message:
            return f"{signal.error_name}: {_clip(signal.error_message, 200)}"
        if signal.error_message:
            return _clip(signal.error_message, 200)
        return "the underlying runtime reported an error"
    if category == "api_failure":
        bad = next(
            (n for n in signal.network if 400 <= n.status_code < 500),
            None,
        )
        if bad is not None:
            return f"HTTP {bad.status_code} from {_short_url(bad.url)}"
        return "an unexpected response status"
    if category == "auth_failure":
        auth = next(
            (n for n in signal.network if n.status_code in {401, 403}),
            None,
        )
        if auth is not None:
            return f"HTTP {auth.status_code} from {_short_url(auth.url)}"
        if signal.error_message:
            return _clip(signal.error_message, 160)
        return "the login fixture did not complete"
    if category == "flake":
        return f"Observed {signal.retries} retries before success."
    if category == "data_setup_failure":
        if signal.error_message:
            return _clip(signal.error_message, 160)
        return "The fixture raised before yielding to the test."
    if category == "performance_regression":
        if signal.error_message:
            return _clip(signal.error_message, 160)
        return "a budget assertion fired"
    if category == "security_finding":
        if signal.error_message:
            return _clip(signal.error_message, 160)
        return "a security assertion fired"
    if category == "accessibility_violation":
        if signal.error_message:
            return _clip(signal.error_message, 160)
        return "an axe assertion fired"
    # unknown
    if signal.error_message:
        return _clip(signal.error_message, 200)
    return "no error message was captured"


def _locator_snippet(signal: FailureSignal) -> str:
    """Pull a short locator name out of the error message if possible."""

    msg = signal.error_message or ""
    # Common Playwright phrasing: ``locator('button[name="Sign in"]')``
    for marker in ("getByRole(", "getByLabel(", "getByText(", "getByPlaceholder("):
        idx = msg.find(marker)
        if idx != -1:
            end = msg.find(")", idx)
            if end != -1:
                return msg[idx : end + 1]
    if "locator(" in msg:
        idx = msg.find("locator(")
        end = msg.find(")", idx)
        if end != -1:
            return msg[idx : end + 1]
    return "the expected element"


def _short_url(url: str, *, max_path: int = 80) -> str:
    """Trim a URL's query/fragment and clip the path for the hypothesis text."""

    base = url.split("?", 1)[0].split("#", 1)[0]
    if len(base) <= max_path:
        return base
    return base[: max_path - 1] + "…"


def _clip(text: str, limit: int) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _collect_evidence_refs(signal: FailureSignal) -> tuple[str, ...]:
    refs: list[str] = []
    for ev in signal.evidence:
        refs.append(ev)
    if signal.error_message and "trace" not in refs:
        # Hint at the trace viewer even when no trace path was captured;
        # the user knows where to find their run's trace dir.
        refs.append("trace://failing-test")
    return tuple(refs)


__all__ = ["hypothesize"]
