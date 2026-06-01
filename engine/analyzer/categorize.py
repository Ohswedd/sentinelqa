"""Failure categorization rules (the documentation, ADR-0014, task 09.01).

The classifier is a small, ordered, deterministic rule set. Each rule
returns ``(category, confidence, rationale)`` if it matches, else
``None``. We collect every match, then pick the highest-confidence one
as the primary category; the others are surfaced as ``secondary``
suggestions so downstream consumers (Reporter, SDK) can show alternative
hypotheses without re-running the rules.

The rules are intentionally narrow — over-broad rules (e.g. "any
5xx → app_bug") would hide legitimate environment failures. When a
signal slips past every rule we return ``unknown`` with low confidence
and a rationale that points the user at the trace.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from engine.analyzer.models import (
    FailureCategory,
    FailureClassification,
    FailureSignal,
)

# A rule returns None for no-match or a 3-tuple for a match.
_Rule = Callable[[FailureSignal], tuple[FailureCategory, float, str] | None]


# ---------------------------------------------------------------------------
# Individual rules (kept top-level so each is unit-testable in isolation)
# ---------------------------------------------------------------------------


def _rule_flake(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    """Pass-on-retry => flake. The runner aggregator marks status='flaky'
    when an earlier attempt failed and a later one passed."""

    if signal.status == "flaky":
        return ("flake", 0.92, "Test passed on a retry after earlier attempts failed.")
    # Multi-attempt where some passed and some failed → flake hint.
    seen_pass = any(a.status == "passed" for a in signal.attempts)
    seen_fail = any(a.status in {"failed", "timed_out"} for a in signal.attempts)
    if seen_pass and seen_fail:
        return ("flake", 0.8, "Test alternated between passing and failing across attempts.")
    return None


def _rule_browser_crash(
    signal: FailureSignal,
) -> tuple[FailureCategory, float, str] | None:
    """Browser crash / OOM / port conflict → environment_failure."""

    name = (signal.error_name or "").lower()
    msg = (signal.error_message or "").lower()
    crash_markers = (
        "target closed",
        "browser has been closed",
        "browser crashed",
        "page crashed",
        "out of memory",
        "eaddrinuse",
        "address already in use",
        "econnrefused",
        "econnreset",
        "playwright was unable to launch",
    )
    if any(marker in msg for marker in crash_markers):
        return (
            "environment_failure",
            0.9,
            "Test runtime crashed (browser/network/host); not an app or test defect.",
        )
    if (
        name in {"timeouterror", "operationtimeouterror"}
        and "navigation" in msg
        and not any(_is_app_5xx(n) for n in signal.network)
    ):
        return (
            "environment_failure",
            0.7,
            "Navigation timed out without any server response — likely network/host issue.",
        )
    return None


def _rule_fixture_auth_failure(
    signal: FailureSignal,
) -> tuple[FailureCategory, float, str] | None:
    """Failure inside the auth fixture → auth_failure."""

    if not signal.fixture_failed:
        return None
    text = f"{signal.error_message or ''} {signal.error_name or ''} {signal.title}".lower()
    if any(
        token in text for token in ("login", "auth", "credential", "sign-in", "sign in", "token")
    ):
        return (
            "auth_failure",
            0.9,
            "Login/auth fixture failed before the test ran.",
        )
    return (
        "data_setup_failure",
        0.8,
        "A non-auth fixture failed before the test body executed.",
    )


def _rule_app_5xx(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    """5xx during the test + assertion failure → app_bug (high)."""

    five_xx = [n for n in signal.network if _is_app_5xx(n)]
    if not five_xx:
        return None
    if signal.status in {"failed", "timed_out"}:
        bad = five_xx[0]
        return (
            "app_bug",
            0.93,
            f"Server returned {bad.status_code} during the failing test.",
        )
    return None


def _rule_api_4xx(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    """4xx (not 401/403) without an assertion → api_failure."""

    bad = [
        n for n in signal.network if 400 <= n.status_code < 500 and n.status_code not in {401, 403}
    ]
    if not bad:
        return None
    first = bad[0]
    return (
        "api_failure",
        0.78,
        f"API responded {first.status_code} during the test — contract or input mismatch.",
    )


def _rule_auth_4xx(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    """401/403 surfaced as the failure cause → auth_failure."""

    auth_codes = [n for n in signal.network if n.status_code in {401, 403}]
    if not auth_codes:
        return None
    return (
        "auth_failure",
        0.82,
        f"Authentication denied ({auth_codes[0].status_code}) during the failing test.",
    )


def _rule_locator_timeout(
    signal: FailureSignal,
) -> tuple[FailureCategory, float, str] | None:
    """Locator timeout but the app responded 200 → test_bug (medium)."""

    msg = (signal.error_message or "").lower()
    name = (signal.error_name or "").lower()
    locator_markers = (
        "locator.",
        "expect(locator",
        "waiting for selector",
        "waiting for locator",
        "element is not visible",
        "no element matches",
        "strict mode violation",
    )
    matched = any(marker in msg for marker in locator_markers)
    if not matched and "timeout" in name and "locator" in msg:
        matched = True
    if not matched:
        return None
    healthy = signal.network and not any(_is_app_5xx(n) for n in signal.network)
    if healthy:
        return (
            "test_bug",
            0.78,
            "Locator timed out while the app responded successfully — selector likely stale.",
        )
    return (
        "test_bug",
        0.6,
        "Locator timed out; app health uncertain from the captured network log.",
    )


def _rule_a11y(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    """Module-level signal: an a11y test failed → accessibility_violation."""

    if signal.module == "a11y":
        return (
            "accessibility_violation",
            0.95,
            "Axe / accessibility assertion fired during the test.",
        )
    msg = (signal.error_message or "").lower()
    if "axe" in msg or "violation" in msg:
        return (
            "accessibility_violation",
            0.7,
            "Axe-style violation surfaced inside a non-a11y test.",
        )
    return None


def _rule_security(signal: FailureSignal) -> tuple[FailureCategory, float, str] | None:
    if signal.module == "security":
        return (
            "security_finding",
            0.9,
            "Security module assertion failed — header/cookie/policy check.",
        )
    return None


def _rule_performance(
    signal: FailureSignal,
) -> tuple[FailureCategory, float, str] | None:
    if signal.module == "performance":
        return (
            "performance_regression",
            0.9,
            "Performance budget (LCP/CLS/INP/api_p95) exceeded.",
        )
    msg = (signal.error_message or "").lower()
    if "budget" in msg and ("exceeded" in msg or "over" in msg):
        return (
            "performance_regression",
            0.7,
            "Budget assertion failed inside a non-performance test.",
        )
    return None


def _rule_data_setup(
    signal: FailureSignal,
) -> tuple[FailureCategory, float, str] | None:
    msg = (signal.error_message or "").lower()
    text = f"{msg} {signal.title.lower()}"
    if (
        ("seed" in text or "fixture" in text or "test data" in text or "factory" in text)
        and "auth" not in text
        and "login" not in text
    ):
        return (
            "data_setup_failure",
            0.72,
            "Test data / seed / fixture step appears to have failed.",
        )
    return None


# Order matters: more specific / higher-confidence rules first. Rules
# never short-circuit — every rule runs so secondary hypotheses are
# preserved.
_RULES: Final[tuple[_Rule, ...]] = (
    _rule_flake,
    _rule_browser_crash,
    _rule_fixture_auth_failure,
    _rule_app_5xx,
    _rule_api_4xx,
    _rule_auth_4xx,
    _rule_locator_timeout,
    _rule_a11y,
    _rule_security,
    _rule_performance,
    _rule_data_setup,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_app_5xx(n: object) -> bool:
    """``True`` when ``n`` is a :class:`NetworkRecord` with 500-599 status."""

    code = getattr(n, "status_code", None)
    return isinstance(code, int) and 500 <= code < 600


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def categorize(signal: FailureSignal) -> FailureClassification:
    """Return the best-fit :class:`FailureClassification` for ``signal``."""

    matches: list[tuple[FailureCategory, float, str]] = []
    for rule in _RULES:
        result = rule(signal)
        if result is not None:
            matches.append(result)

    if not matches:
        return FailureClassification(
            category="unknown",
            confidence=0.3,
            rationale=(
                "No rule matched; inspect the trace and console log for "
                "context. The failure may be a novel pattern."
            ),
        )

    # Stable sort: highest confidence first; ties broken by rule order.
    ranked = sorted(
        ((i, m) for i, m in enumerate(matches)),
        key=lambda kv: (-kv[1][1], kv[0]),
    )
    primary_idx, primary = ranked[0]
    secondary = tuple((cat, conf) for _, (cat, conf, _) in ranked[1:] if cat != primary[0])
    return FailureClassification(
        category=primary[0],
        confidence=primary[1],
        rationale=primary[2],
        secondary=secondary,
    )


# ---------------------------------------------------------------------------
# Module-error categorization (CLAUDE §10 catch-all rehome, task 09.01)
# ---------------------------------------------------------------------------


def categorize_module_error(
    *,
    module: str,
    exc_type: str,
    exc_message: str,
) -> FailureClassification:
    """Categorize a module-level exception caught by ``run_modules``.

    Phase 02's lifecycle wraps every module call in a broad ``except
    Exception`` (CLAUDE §10) and stuffs the result into a string. Phase
    09 adds a typed classification so the reporter / SDK can show the
    user *why* a module fell over — not just "errored".

    Heuristics are intentionally light: a module error before any tests
    ran is almost always environment or import-time; richer
    categorization happens once test signals exist.
    """

    name = (exc_type or "").lower()
    msg = (exc_message or "").lower()

    if name in {
        "modulenotfounderror",
        "importerror",
        "filenotfounderror",
        "permissionerror",
    }:
        return FailureClassification(
            category="environment_failure",
            confidence=0.9,
            rationale=f"Module '{module}' failed to load: {exc_type}.",
        )
    if name in {"connectionerror", "connectionrefusederror", "timeouterror", "oserror"}:
        return FailureClassification(
            category="environment_failure",
            confidence=0.85,
            rationale=f"Module '{module}' failed on network/host: {exc_type}.",
        )
    if name == "unsafetargeterror" or "unsafe" in msg:
        return FailureClassification(
            category="environment_failure",
            confidence=0.95,
            rationale=f"Safety policy blocked module '{module}'.",
        )
    if name in {"testexecutionerror"} or "test" in msg and "execution" in msg:
        return FailureClassification(
            category="test_bug",
            confidence=0.7,
            rationale=f"Module '{module}' raised TestExecutionError; suite likely malformed.",
        )
    if name == "configerror":
        return FailureClassification(
            category="environment_failure",
            confidence=0.9,
            rationale=f"Module '{module}' rejected the run config.",
        )
    # Default: low-confidence environment — Phase 09 prefers to under-claim
    # rather than mis-blame the app.
    return FailureClassification(
        category="environment_failure",
        confidence=0.45,
        rationale=(
            f"Module '{module}' raised an unrecognized {exc_type or 'error'} before "
            "producing per-test signals; inspect logs/<module>.log for context."
        ),
    )


__all__ = ["categorize", "categorize_module_error"]
