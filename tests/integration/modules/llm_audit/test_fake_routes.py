"""Integration tests for fake-route / fake-endpoint checks (task 19.03)."""

from __future__ import annotations

from modules.llm_audit.checks.fake_routes import (
    _normalize_path,
    _path_template,
    check_fake_endpoints,
    check_fake_routes,
)
from modules.llm_audit.models import ApiReference, LinkReference


def test_normalize_path_strips_trailing_slash() -> None:
    assert _normalize_path("/foo/") == "/foo"
    assert _normalize_path("/") == "/"
    assert _normalize_path("http://localhost/foo/bar/") == "/foo/bar"


def test_path_template_replaces_uuid_and_numeric() -> None:
    assert _path_template("/users/123") == "/users/[id]"
    assert _path_template("/items/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee") == "/items/[uuid]"


def test_link_to_observed_route_is_clean() -> None:
    findings = check_fake_routes(
        [LinkReference(source_route="/", target_path="/dashboard")],
        observed_routes=["/dashboard"],
        observed_route_status={"/dashboard": 200},
    )
    assert findings == ()


def test_link_to_404_triggers_fake_route() -> None:
    findings = check_fake_routes(
        [LinkReference(source_route="/", target_path="/missing")],
        observed_routes=["/"],
        observed_route_status={"/": 200, "/missing": 404},
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-FAKE-ROUTE"
    assert findings[0].route == "/"


def test_link_to_unobserved_route_lowers_confidence() -> None:
    findings = check_fake_routes(
        [LinkReference(source_route="/", target_path="/never-seen")],
        observed_routes=["/", "/dashboard"],
        observed_route_status={"/": 200, "/dashboard": 200},
    )
    assert len(findings) == 1
    assert findings[0].confidence_override == 0.7


def test_endpoint_in_observed_traffic_is_clean() -> None:
    findings = check_fake_endpoints(
        [ApiReference(path="/api/orders", method="POST")],
        observed_endpoints=[("POST", "/api/orders")],
        openapi_endpoints=(),
    )
    assert findings == ()


def test_endpoint_in_openapi_is_clean() -> None:
    findings = check_fake_endpoints(
        [ApiReference(path="/api/orders", method="POST")],
        observed_endpoints=(),
        openapi_endpoints=[("POST", "/api/orders")],
    )
    assert findings == ()


def test_endpoint_with_id_segment_matches_template() -> None:
    findings = check_fake_endpoints(
        [ApiReference(path="/api/users/42", method="GET")],
        observed_endpoints=[("GET", "/api/users/[id]")],
        openapi_endpoints=(),
    )
    assert findings == ()


def test_unknown_endpoint_is_flagged() -> None:
    findings = check_fake_endpoints(
        [
            ApiReference(
                path="/api/imaginary",
                method="POST",
                source_file="src/lib/api.ts",
            )
        ],
        observed_endpoints=(),
        openapi_endpoints=(),
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-FAKE-ENDPOINT"
    assert findings[0].file == "src/lib/api.ts"
