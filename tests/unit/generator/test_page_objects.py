"""Tests for the page-object generator."""

from __future__ import annotations

from pathlib import Path

from engine.domain.element import Element
from engine.domain.flow import Flow, FlowStep
from engine.domain.ids import IdGenerator
from engine.domain.route import Route
from engine.generator.page_objects import (
    PageObjectOptions,
    generate_page_objects,
    route_to_page_name,
)


def _ids() -> IdGenerator:
    return IdGenerator()


def test_route_to_page_name_for_root() -> None:
    assert route_to_page_name("/") == "RootPage"


def test_route_to_page_name_for_nested() -> None:
    assert route_to_page_name("/users/[id]/edit") == "UsersIdEditPage"
    assert route_to_page_name("/api/v1/foo") == "ApiV1FooPage"


def test_emits_page_object_when_elements_threshold_met() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/login")
    els = [
        Element(
            id=ids.new("EL"), role="textbox", accessible_name="Email", selector="#e", route_id=r.id
        ),
        Element(
            id=ids.new("EL"),
            role="textbox",
            accessible_name="Password",
            selector="#p",
            route_id=r.id,
        ),
        Element(
            id=ids.new("EL"),
            role="button",
            accessible_name="Sign in",
            selector="button",
            route_id=r.id,
        ),
    ]
    objs = generate_page_objects(routes=[r], elements=els, flows=[], out_dir=Path("."))
    assert len(objs) == 1
    obj = objs[0]
    assert obj.class_name == "LoginPage"
    assert obj.accessor_count == 3
    assert "page.getByRole('textbox', { name: \"Email\" })" in obj.source
    assert "page.getByRole('button', { name: \"Sign in\" })" in obj.source
    # Page object source ALWAYS carries the SentinelQA banner.
    assert "SentinelQA Generated" in obj.source


def test_skips_route_below_threshold() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/seldom-used")
    els = [
        Element(
            id=ids.new("EL"), role="textbox", accessible_name="x", selector="#x", route_id=r.id
        ),
    ]
    objs = generate_page_objects(routes=[r], elements=els, flows=[], out_dir=Path("."))
    assert objs == []


def test_route_with_two_flows_qualifies_even_without_elements() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/dashboard")
    flows = []
    for _ in range(2):
        flows.append(
            Flow(
                id=ids.new("FLW"),
                name="x",
                steps=(FlowStep(description="go", target_route_id=r.id, expected_outcome="ok"),),
            )
        )
    objs = generate_page_objects(routes=[r], elements=[], flows=flows, out_dir=Path("."))
    assert len(objs) == 1
    assert objs[0].accessor_count == 0
    assert "no semantic accessors generated" in objs[0].source


def test_skips_element_without_accessible_name() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/items")
    els = [
        Element(id=ids.new("EL"), role="link", accessible_name="Open", selector="a", route_id=r.id),
        # No accessible name → skipped.
        Element(id=ids.new("EL"), role="link", accessible_name=None, selector="a", route_id=r.id),
        Element(
            id=ids.new("EL"), role="link", accessible_name="Close", selector="a", route_id=r.id
        ),
    ]
    objs = generate_page_objects(routes=[r], elements=els, flows=[], out_dir=Path("."))
    assert len(objs) == 1
    assert objs[0].accessor_count == 2
    assert len(objs[0].skipped_elements) == 1


def test_output_is_deterministic_for_same_input() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/login")
    els = [
        Element(
            id=ids.new("EL"), role="textbox", accessible_name="Email", selector="#e", route_id=r.id
        ),
        Element(
            id=ids.new("EL"),
            role="textbox",
            accessible_name="Password",
            selector="#p",
            route_id=r.id,
        ),
        Element(
            id=ids.new("EL"), role="button", accessible_name="Sign in", selector="b", route_id=r.id
        ),
    ]
    a = generate_page_objects(routes=[r], elements=els, flows=[], out_dir=Path("."))
    b = generate_page_objects(routes=[r], elements=els, flows=[], out_dir=Path("."))
    assert a[0].source == b[0].source


def test_options_threshold_tuning() -> None:
    ids = _ids()
    r = Route(id=ids.new("RT"), path="/x")
    els = [
        Element(id=ids.new("EL"), role="link", accessible_name="Link", selector="a", route_id=r.id),
    ]
    objs = generate_page_objects(
        routes=[r],
        elements=els,
        flows=[],
        out_dir=Path("."),
        options=PageObjectOptions(min_flow_uses=1, min_elements=1),
    )
    assert len(objs) == 1
