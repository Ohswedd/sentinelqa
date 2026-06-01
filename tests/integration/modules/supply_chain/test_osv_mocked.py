"""OSV lookup integration tests against ``httpx.MockTransport``.

We never hit ``api.osv.dev`` in CI. The mock transport simulates
happy / 429 / 500 / network-error paths so we can prove the offline
degradation contract from the README.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from modules.supply_chain.models import SbomComponent, SbomDocument, SbomLockfileResult
from modules.supply_chain.osv import (
    query_osv,
    run_osv_lookup_from_sbom,
)


def _component(name: str, version: str, ecosystem: str = "PyPI") -> SbomComponent:
    return SbomComponent(
        name=name,
        version=version,
        ecosystem=ecosystem,  # type: ignore[arg-type]
        purl=f"pkg:{'pypi' if ecosystem == 'PyPI' else 'npm'}/{name}@{version}",
    )


def _sbom_with(components: tuple[SbomComponent, ...]) -> SbomDocument:
    return SbomDocument(
        generated_at=datetime(2026, 5, 31, tzinfo=UTC),
        project_name="test",
        lockfiles=(
            SbomLockfileResult(
                path="requirements.txt",
                kind="requirements.txt",
                ecosystem="PyPI",
                components=components,
            ),
        ),
        components_count=len(components),
    )


def _mock_transport(
    handler: callable,  # type: ignore[valid-type]
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_query_osv_happy_path() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "vulns": [
                            {
                                "id": "GHSA-real",
                                "summary": "test",
                                "severity": [{"type": "CVSS_V3", "score": "7.5"}],
                                "database_specific": {"cwe_ids": ["CWE-22"]},
                                "affected": [{"ranges": [{"events": [{"fixed": "2.32.0"}]}]}],
                            }
                        ]
                    }
                ]
            },
        )

    transport = _mock_transport(handler)
    report = query_osv(
        components=(_component("requests", "2.31.0"),),
        rate_limit_rps=1000.0,
        transport=transport,
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert not report.skipped
    assert report.components_count == 1
    assert report.vulnerabilities[0].advisories[0].fixed_in == "2.32.0"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["queries"][0]["package"]["ecosystem"] == "PyPI"


def test_query_osv_429_marks_skipped() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    report = query_osv(
        components=(_component("requests", "2.31.0"),),
        rate_limit_rps=1000.0,
        transport=_mock_transport(handler),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert report.skipped is True
    assert report.skipped_reason and "OSV unreachable" in report.skipped_reason


def test_query_osv_500_marks_skipped() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    report = query_osv(
        components=(_component("requests", "2.31.0"),),
        rate_limit_rps=1000.0,
        transport=_mock_transport(handler),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert report.skipped is True


def test_query_osv_offline_marks_skipped() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    report = query_osv(
        components=(_component("requests", "2.31.0"),),
        rate_limit_rps=1000.0,
        transport=_mock_transport(handler),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert report.skipped is True
    assert "OSV unreachable" in (report.skipped_reason or "")


def test_query_osv_empty_components_returns_clean_report() -> None:
    report = query_osv(components=(), rate_limit_rps=1000.0)
    assert report.components_count == 0
    assert report.vulnerabilities == ()
    assert report.skipped is False


def test_run_osv_lookup_disabled_path() -> None:
    sbom = _sbom_with((_component("requests", "2.31.0"),))
    report = run_osv_lookup_from_sbom(sbom=sbom, enabled=False)
    assert report.skipped is True
    assert report.skipped_reason == "policy.supply_chain.osv.enabled is false"


def test_run_osv_lookup_dedups_components() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"results": [{}, {}]})

    sbom = SbomDocument(
        generated_at=datetime(2026, 5, 31, tzinfo=UTC),
        project_name="dedupe",
        lockfiles=(
            SbomLockfileResult(
                path="a.txt",
                kind="requirements.txt",
                ecosystem="PyPI",
                components=(_component("requests", "2.31.0"),),
            ),
            SbomLockfileResult(
                path="b.txt",
                kind="requirements.txt",
                ecosystem="PyPI",
                components=(_component("requests", "2.31.0"), _component("flask", "3.0.0")),
            ),
        ),
        components_count=2,
    )
    report = run_osv_lookup_from_sbom(
        sbom=sbom,
        rate_limit_rps=1000.0,
        transport=_mock_transport(handler),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    body = captured["body"]
    assert isinstance(body, dict)
    queries = body["queries"]
    assert len(queries) == 2
    assert report.components_count == 2
