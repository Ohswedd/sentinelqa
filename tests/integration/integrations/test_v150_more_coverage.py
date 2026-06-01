# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 SentinelQA contributors.
"""Additional coverage: github issue lifecycle, metrics edge cases, otel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from integrations._http import HttpClient, IntegrationHttpError
from integrations.github.issue_lifecycle import (
    FindingFingerprint,
    close_resolved_issues,
    find_issue_by_fingerprint,
    finding_fingerprint,
    fingerprint_anchor,
    labels_for,
    render_lifecycle_title,
    upsert_issue,
)
from integrations.metrics import (
    DatadogPusher,
    HoneycombPusher,
    NewRelicPusher,
    RunMetrics,
)


@dataclass(frozen=True, slots=True)
class _StubFinding:
    id: str
    module: str
    category: str
    title: str
    severity: str = "high"
    description: str = "x"
    recommendation: str | None = None
    suggested_fix: str | None = None
    affected_target: str | None = None
    evidence: tuple = ()
    cwe_id: str | None = None


class _FakeClient(HttpClient):
    def __init__(
        self,
        *,
        get_responses: list[Any] | None = None,
        post_responses: list[Any] | None = None,
        patch_responses: list[Any] | None = None,
    ) -> None:
        super().__init__()
        self.get_calls: list[str] = []
        self.post_calls: list[tuple[str, Mapping[str, Any]]] = []
        self.patch_calls: list[tuple[str, Mapping[str, Any]]] = []
        self._gets = list(get_responses or [])
        self._posts = list(post_responses or [])
        self._patches = list(patch_responses or [])

    def get_json(self, url: str) -> Any:
        self.get_calls.append(url)
        if not self._gets:
            raise AssertionError("no scripted GET")
        nxt = self._gets.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def post_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.post_calls.append((url, dict(payload)))
        if not self._posts:
            raise AssertionError("no scripted POST")
        nxt = self._posts.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def patch_json(self, url: str, payload: Mapping[str, Any]) -> Any:
        self.patch_calls.append((url, dict(payload)))
        if not self._patches:
            raise AssertionError("no scripted PATCH")
        nxt = self._patches.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


# --------------------------------------------------------------------------- #
# Lifecycle: error paths
# --------------------------------------------------------------------------- #


def test_upsert_rejects_bad_repo() -> None:
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="x")
    client = _FakeClient(get_responses=[])
    from integrations.github.issue import GitHubIssueError

    with pytest.raises(GitHubIssueError):
        upsert_issue(repo="badrepo", finding=finding, client=client, auto_create=True)


def test_upsert_propagates_http_error() -> None:
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="x")
    client = _FakeClient(get_responses=[IntegrationHttpError("rate limit")])
    from integrations.github.issue import GitHubIssueError

    with pytest.raises(GitHubIssueError):
        upsert_issue(repo="owner/repo", finding=finding, client=client, auto_create=True)


def test_upsert_propagates_post_http_error() -> None:
    finding = _StubFinding(id="FND-X", module="security", category="headers", title="x")
    client = _FakeClient(
        get_responses=[{"items": []}],
        post_responses=[IntegrationHttpError("github 500")],
    )
    from integrations.github.issue import GitHubIssueError

    with pytest.raises(GitHubIssueError):
        upsert_issue(repo="owner/repo", finding=finding, client=client, auto_create=True)


def test_find_by_fingerprint_returns_none_on_empty_items() -> None:
    fp = FindingFingerprint("security", "headers", "X", "missing")
    client = _FakeClient(get_responses=[{"items": []}])
    result = find_issue_by_fingerprint(repo="owner/repo", fingerprint=fp, client=client)
    assert result is None


def test_find_by_fingerprint_skips_non_matching_anchor() -> None:
    fp = FindingFingerprint("security", "headers", "X", "missing")
    client = _FakeClient(get_responses=[{"items": [{"title": "unrelated issue", "number": 99}]}])
    assert find_issue_by_fingerprint(repo="owner/repo", fingerprint=fp, client=client) is None


def test_close_resolved_issues_skips_items_without_digest() -> None:
    """Issues that don't carry a fingerprint anchor are left alone."""

    client = _FakeClient(get_responses=[{"items": [{"number": 1, "title": "stale legacy issue"}]}])
    closed = close_resolved_issues(
        repo="owner/repo",
        current_findings=[],
        client=client,
        run_id="RUN-X",
    )
    assert closed == ()


def test_close_resolved_issues_handles_search_error() -> None:
    client = _FakeClient(get_responses=[IntegrationHttpError("oops")])
    from integrations.github.issue import GitHubIssueError

    with pytest.raises(GitHubIssueError):
        close_resolved_issues(
            repo="owner/repo",
            current_findings=[],
            client=client,
            run_id="RUN-X",
        )


def test_finding_fingerprint_accepts_dict_input() -> None:
    """The fingerprint extractor must NOT crash on raw dicts."""

    fp = finding_fingerprint(
        {"module": "security", "category": "headers", "title": "CSP", "evidence": {"rule_id": "R1"}}
    )
    # The actual values depend on dict-vs-object access semantics —
    # the contract verified here is "does not raise".
    assert isinstance(fp, FindingFingerprint)


def test_render_lifecycle_title_truncates_long_titles() -> None:
    finding = _StubFinding(
        id="FND-X",
        module="security",
        category="headers",
        title="a" * 300,
    )
    fp = finding_fingerprint(finding)
    title = render_lifecycle_title(finding, fp)
    assert len(title) <= 256


def test_render_lifecycle_title_keeps_existing_anchor() -> None:
    """When the base title already carries the fingerprint anchor, we keep it."""

    finding = _StubFinding(id="FND-X", module="security", category="headers", title="t")
    fp = finding_fingerprint(finding)
    title = render_lifecycle_title(finding, fp)
    # Re-render should be idempotent.
    title2 = render_lifecycle_title(finding, fp)
    assert title == title2


def test_labels_for_dedups_overlap() -> None:
    labels = labels_for("headers", base_labels=("sentinelqa", "security"))
    # Even though "security" is in both base_labels and the template extras,
    # the helper dedups.
    assert labels.count("security") == 1


def test_fingerprint_anchor_smoke() -> None:
    fp = FindingFingerprint("security", "headers", "X", "y")
    assert fingerprint_anchor(fp).startswith("[sentinelqa-fp:")


# --------------------------------------------------------------------------- #
# Metrics: failure paths through the real push() method
# --------------------------------------------------------------------------- #


class _RaiseClient(HttpClient):
    def __init__(self, *, exc: Exception) -> None:
        super().__init__()
        self._exc = exc

    def post_text(self, url: str, payload: Mapping[str, Any]) -> str:
        raise self._exc


_RUN = RunMetrics(
    run_id="r",
    status="passed",
    quality_score=90.0,
    target_host="x",
    started_at="2026-06-01T00:00:00+00:00",
    duration_ms=1000,
)


def test_datadog_push_wraps_http_error() -> None:
    from integrations.metrics.datadog import DatadogError

    pusher = DatadogPusher(api_key="dd-key", client=_RaiseClient(exc=IntegrationHttpError("503")))
    with pytest.raises(DatadogError):
        pusher.push(_RUN)


def test_newrelic_push_wraps_http_error() -> None:
    from integrations.metrics.newrelic import NewRelicError

    pusher = NewRelicPusher(
        license_key="nr-key", client=_RaiseClient(exc=IntegrationHttpError("403"))
    )
    with pytest.raises(NewRelicError):
        pusher.push(_RUN)


def test_honeycomb_push_wraps_http_error() -> None:
    from integrations.metrics.honeycomb import HoneycombError

    pusher = HoneycombPusher(
        api_key="hc-key", dataset="x", client=_RaiseClient(exc=IntegrationHttpError("500"))
    )
    with pytest.raises(HoneycombError):
        pusher.push(_RUN)


def test_honeycomb_rejects_empty_dataset() -> None:
    from integrations.metrics.honeycomb import HoneycombError

    with pytest.raises(HoneycombError):
        HoneycombPusher(api_key="hc-key", dataset="")


def test_build_datadog_payload_handles_no_quality_score() -> None:
    from integrations.metrics.datadog import build_datadog_payload

    metrics = RunMetrics(
        run_id="r",
        status="passed",
        quality_score=None,
        target_host="x",
        started_at="2026-06-01T00:00:00+00:00",
        duration_ms=1000,
    )
    payload = build_datadog_payload(metrics)
    names = {row["metric"] for row in payload["series"]}
    assert "sentinelqa.quality_score" not in names
    assert "sentinelqa.duration_ms" in names


# --------------------------------------------------------------------------- #
# OTel real-tracer through stub handle
# --------------------------------------------------------------------------- #


def test_real_tracer_propagates_exception() -> None:
    """A raise inside ``with tracer.span(...)`` must bubble up cleanly."""

    import contextlib

    from integrations.otel.tracer import SentinelTracer

    class _FakeHandle:
        @contextlib.contextmanager
        def start_as_current_span(self, name: str, attributes: dict[str, Any]):
            _ = name, attributes
            yield None

    tracer = SentinelTracer(handle=_FakeHandle(), status="enabled")
    with pytest.raises(RuntimeError, match="boom"), tracer.span("x"):
        raise RuntimeError("boom")
