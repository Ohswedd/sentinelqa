# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Unit tests for browser-side forensics → Finding conversion."""

from __future__ import annotations

import pytest
from engine.orchestrator.ts_bridge import NetworkFailureEvent, PageErrorEvent
from engine.runner.forensics import (
    CATEGORY_NETWORK_5XX,
    CATEGORY_PAGE_ERROR,
    forensics_from_events,
    network_failure_to_finding,
    page_error_to_finding,
    severity_for_failing_test,
)

_RUN_ID = "RUN-PASSEDAAAAAA"


def _page_error(
    *,
    test_id: str | None = "t-1",
    name: str = "TypeError",
    message: str = "x is undefined",
    stack: str = "    at https://example.com/app.js:1:2",
    source_url: str = "https://example.com/app.js",
) -> PageErrorEvent:
    return PageErrorEvent(
        schema_version="1.0.0",
        seq=1,
        ts="2026-06-01T00:00:00.000Z",
        type="page.error",
        test_id=test_id,
        name=name,
        message=message,
        stack=stack,
        source_url=source_url,
    )


def _network_failure(
    *,
    test_id: str | None = "t-1",
    status: int = 502,
    method: str = "GET",
    url: str = "https://api.example.com/users",
    body: str = "<html>bad gateway</html>",
) -> NetworkFailureEvent:
    return NetworkFailureEvent(
        schema_version="1.0.0",
        seq=1,
        ts="2026-06-01T00:00:00.000Z",
        type="network.failure",
        test_id=test_id,
        request_id="req-1",
        url=url,
        method=method,
        status=status,
        request_headers={"User-Agent": "ua"},
        response_headers={"content-type": "text/html"},
        response_body_preview=body,
        duration_ms=42,
    )


def test_page_error_converts_to_finding() -> None:
    f = page_error_to_finding(
        _page_error(),
        run_id=_RUN_ID,
        module="functional",
    )
    assert f.category == CATEGORY_PAGE_ERROR
    assert f.severity == "medium"
    assert f.cwe_id == "CWE-754"
    assert "TypeError" in f.title
    assert "x is undefined" in f.description
    assert "https://example.com/app.js" in (f.location.file or "")


def test_page_error_severity_bumps_when_test_failed() -> None:
    f = page_error_to_finding(
        _page_error(),
        run_id=_RUN_ID,
        module="functional",
        test_failed=True,
    )
    assert f.severity == "high"


def test_network_failure_converts_to_finding() -> None:
    f = network_failure_to_finding(
        _network_failure(),
        run_id=_RUN_ID,
        module="api",
    )
    assert f.category == CATEGORY_NETWORK_5XX
    assert f.severity == "high"
    assert f.cwe_id == "CWE-755"
    assert "502" in f.title
    assert "bad gateway" in f.description
    assert "Request headers" in f.description
    assert "Response headers" in f.description


def test_network_failure_severity_bumps_to_critical_on_failing_test() -> None:
    f = network_failure_to_finding(
        _network_failure(),
        run_id=_RUN_ID,
        module="api",
        test_failed=True,
    )
    assert f.severity == "critical"


def test_forensics_from_events_filters_and_routes() -> None:
    events = [
        _page_error(test_id="t-1"),
        _network_failure(test_id="t-1", status=503),
        _page_error(test_id="t-2"),
    ]
    findings = forensics_from_events(
        events,
        run_id=_RUN_ID,
        module="functional",
        failing_test_ids=frozenset({"t-1"}),
    )
    assert len(findings) == 3
    assert any("503" in f.title for f in findings)
    ids = {f.id for f in findings}
    assert len(ids) == 3


def test_severity_helper_handles_unknown_default() -> None:
    assert severity_for_failing_test("low", False) == "low"
    assert severity_for_failing_test("low", True) == "critical"


def test_network_failure_handles_empty_body_preview() -> None:
    event = _network_failure(body="")
    f = network_failure_to_finding(event, run_id=_RUN_ID, module="api")
    assert "Response body preview" not in f.description


def test_forensics_ignores_non_target_events() -> None:
    from engine.orchestrator.ts_bridge import ConsoleEvent

    events = [
        ConsoleEvent(
            schema_version="1.0.0",
            seq=1,
            ts="2026-06-01T00:00:00.000Z",
            type="console",
            test_id="t-1",
            level="warn",
            message="hi",
            source="",
        ),
        _page_error(),
    ]
    findings = forensics_from_events(events, run_id=_RUN_ID, module="functional")
    assert len(findings) == 1
    assert findings[0].category == CATEGORY_PAGE_ERROR


def test_page_error_description_is_capped_at_7990_chars() -> None:
    """Even an at-max-length message + long stack must fit in the description cap."""

    long_msg = "x" * 7500
    long_stack = "y" * 12000
    f = page_error_to_finding(
        _page_error(message=long_msg, stack=long_stack),
        run_id=_RUN_ID,
        module="functional",
    )
    assert len(f.description) <= 7990


def test_findings_have_unique_ids_per_event() -> None:
    events = [_page_error(), _page_error(), _network_failure()]
    findings = forensics_from_events(events, run_id=_RUN_ID, module="functional")
    ids = [f.id for f in findings]
    assert len(set(ids)) == 3


def test_network_failure_status_must_be_5xx() -> None:
    with pytest.raises(Exception):  # noqa: B017
        _network_failure(status=200)
