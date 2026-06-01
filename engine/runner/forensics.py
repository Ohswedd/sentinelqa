# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Convert browser-side captures into typed :class:`Finding` objects.

The TypeScript runtime captures two new classes of evidence in
``v1.3.0``:

* ``page.error`` — every unhandled browser exception (window-level
  errors + unhandled promise rejections).
* ``network.failure`` — a 5xx response observed during a test, with
  the request + response headers (already redacted) and a bounded
  body preview attached.

These were previously invisible. This module reads them off the
event stream and translates each into a :class:`Finding` so the
audit's scoring, reporter, and CI surface treat them like every
other class of issue.

The conversion is intentionally pure (no IO): tests feed a list of
events and assert on the resulting findings.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Final

from engine.domain.finding import Finding, FindingLocation
from engine.domain.ids import IdGenerator
from engine.orchestrator.ts_bridge import (
    NetworkFailureEvent,
    PageErrorEvent,
    _EventBase,
)

# Category strings (module-scoped — modules pick their own).
CATEGORY_PAGE_ERROR: Final[str] = "page-error"
CATEGORY_NETWORK_5XX: Final[str] = "network-5xx"

# Severity ladder — a single 5xx during a happy-path flow is a "high"
# signal; an uncaught browser exception is "medium" because it's
# very common to see one or two on a real-world page even when the
# flow nominally succeeds. Both ratchet up when they occur on a
# failing test (caller may bump severity via ``severity_for_failing_test``).
_DEFAULT_PAGE_ERROR_SEVERITY = "medium"
_DEFAULT_5XX_SEVERITY = "high"


def severity_for_failing_test(default: str, test_failed: bool) -> str:
    """Bump severity when the corresponding test reported failure."""

    if not test_failed:
        return default
    return "high" if default == "medium" else "critical"


def page_error_to_finding(
    event: PageErrorEvent,
    *,
    run_id: str,
    module: str,
    id_generator: IdGenerator | None = None,
    test_failed: bool = False,
) -> Finding:
    """Convert one ``page.error`` event into a :class:`Finding`."""

    gen = id_generator or IdGenerator()
    severity = severity_for_failing_test(_DEFAULT_PAGE_ERROR_SEVERITY, test_failed)
    title = f"Unhandled browser exception: {event.name}"
    description_parts = [
        f"{event.name}: {event.message}".strip(),
    ]
    if event.stack:
        description_parts.append("Stack (redacted):")
        description_parts.append(event.stack)
    if event.source_url:
        description_parts.append(f"Source: {event.source_url}")
    description = "\n\n".join(description_parts)
    return Finding(
        id=gen.new("FND"),
        run_id=run_id,
        module=module,
        category=CATEGORY_PAGE_ERROR,
        severity=severity,  # type: ignore[arg-type]
        confidence=1.0,
        title=title[:298],
        description=description[:7990] or "(empty page error)",
        location=FindingLocation(
            route=None,
            file=event.source_url or None,
        ),
        reproduction_steps=(
            "Re-run the test that triggered the error.",
            "Open DevTools -> Console; the captured exception will resurface.",
        ),
        suggested_fix=(
            "Add a window-level error handler (window.onerror / "
            "addEventListener('error')) and a top-level try/catch around the "
            "code path indicated by the stack trace."
        ),
        cwe_id="CWE-754",
        created_at=datetime.now(UTC),
    )


def network_failure_to_finding(
    event: NetworkFailureEvent,
    *,
    run_id: str,
    module: str,
    id_generator: IdGenerator | None = None,
    test_failed: bool = False,
) -> Finding:
    """Convert one ``network.failure`` event into a :class:`Finding`."""

    gen = id_generator or IdGenerator()
    severity = severity_for_failing_test(_DEFAULT_5XX_SEVERITY, test_failed)
    title = f"{event.method} {event.url} returned {event.status}"
    description_parts = [
        "A 5xx response was observed during the test.",
        f"Method: {event.method}",
        f"URL:    {event.url}",
        f"Status: {event.status}",
        f"Latency: {event.duration_ms} ms",
        "",
        "Request headers (redacted):",
        _format_headers(event.request_headers),
        "",
        "Response headers (redacted):",
        _format_headers(event.response_headers),
    ]
    if event.response_body_preview:
        description_parts.append("")
        description_parts.append("Response body preview (redacted):")
        description_parts.append(event.response_body_preview[:2048])
    description = "\n".join(description_parts)
    return Finding(
        id=gen.new("FND"),
        run_id=run_id,
        module=module,
        category=CATEGORY_NETWORK_5XX,
        severity=severity,  # type: ignore[arg-type]
        confidence=1.0,
        title=title[:298],
        description=description[:7990],
        location=FindingLocation(route=event.url[:2048]),
        reproduction_steps=(
            "Reproduce the user flow exercised by the failing test.",
            "Observe the 5xx on the listed endpoint in DevTools -> Network.",
        ),
        suggested_fix=(
            "Inspect server logs for the listed URL; map the 5xx to the "
            "underlying exception. If the 5xx is expected (e.g. third-party "
            "outage), gate the affected user-flow on circuit-breaker logic."
        ),
        cwe_id="CWE-755",
        created_at=datetime.now(UTC),
    )


def forensics_from_events(
    events: Iterable[_EventBase],
    *,
    run_id: str,
    module: str,
    failing_test_ids: frozenset[str] = frozenset(),
    id_generator: IdGenerator | None = None,
) -> tuple[Finding, ...]:
    """Walk an event stream and return findings for page errors + 5xx."""

    gen = id_generator or IdGenerator()
    out: list[Finding] = []
    for event in events:
        if isinstance(event, PageErrorEvent):
            test_failed = (event.test_id or "") in failing_test_ids
            out.append(
                page_error_to_finding(
                    event,
                    run_id=run_id,
                    module=module,
                    id_generator=gen,
                    test_failed=test_failed,
                )
            )
        elif isinstance(event, NetworkFailureEvent):
            test_failed = (event.test_id or "") in failing_test_ids
            out.append(
                network_failure_to_finding(
                    event,
                    run_id=run_id,
                    module=module,
                    id_generator=gen,
                    test_failed=test_failed,
                )
            )
    return tuple(out)


def _format_headers(headers: dict[str, str]) -> str:
    if not headers:
        return "(no headers captured)"
    return "\n".join(f"{k}: {v}" for k, v in sorted(headers.items()))


__all__ = [
    "CATEGORY_NETWORK_5XX",
    "CATEGORY_PAGE_ERROR",
    "forensics_from_events",
    "network_failure_to_finding",
    "page_error_to_finding",
    "severity_for_failing_test",
]
