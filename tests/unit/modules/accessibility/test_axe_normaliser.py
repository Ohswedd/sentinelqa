"""Unit tests for :mod:`modules.accessibility.axe_runner`."""

from __future__ import annotations

from modules.accessibility.axe_runner import (
    axe_violations_from_list,
    axe_violations_from_payload,
)


def test_payload_without_violations_key_returns_empty() -> None:
    assert axe_violations_from_payload({}) == ()


def test_payload_with_non_list_violations_returns_empty() -> None:
    assert axe_violations_from_payload({"violations": "nope"}) == ()


def test_skips_entries_without_rule_id() -> None:
    assert axe_violations_from_list([{"impact": "serious"}, {"id": ""}, {}]) == ()


def test_skips_non_dict_entries() -> None:
    assert axe_violations_from_list(["string", 42, None]) == ()


def test_unknown_impact_defaults_to_moderate() -> None:
    violations = axe_violations_from_list([{"id": "x", "impact": "bogus", "tags": [], "nodes": []}])
    assert violations[0].impact == "moderate"


def test_missing_impact_defaults_to_moderate() -> None:
    violations = axe_violations_from_list([{"id": "x", "tags": [], "nodes": []}])
    assert violations[0].impact == "moderate"


def test_non_string_tag_entries_are_filtered() -> None:
    violations = axe_violations_from_list(
        [{"id": "x", "impact": "serious", "tags": ["wcag2aa", 123, None], "nodes": []}]
    )
    assert violations[0].tags == ("wcag2aa",)


def test_nodes_with_string_target_are_normalised() -> None:
    violations = axe_violations_from_list(
        [
            {
                "id": "x",
                "impact": "serious",
                "tags": [],
                "nodes": [{"target": "body", "html": "<body>"}],
            }
        ]
    )
    assert violations[0].nodes[0].target == ("body",)


def test_nodes_with_mixed_target_array_filtered() -> None:
    violations = axe_violations_from_list(
        [
            {
                "id": "x",
                "impact": "minor",
                "tags": [],
                "nodes": [{"target": ["#a", 1, "div"], "html": ""}],
            }
        ]
    )
    assert violations[0].nodes[0].target == ("#a", "div")


def test_help_url_can_use_alternate_key() -> None:
    violations = axe_violations_from_list(
        [
            {
                "id": "x",
                "impact": "moderate",
                "tags": [],
                "nodes": [],
                "help_url": "https://example.test/x",
            }
        ]
    )
    assert violations[0].help_url == "https://example.test/x"


def test_experimental_tag_sets_flag() -> None:
    violations = axe_violations_from_list(
        [{"id": "x", "impact": "moderate", "tags": ["experimental"], "nodes": []}]
    )
    assert violations[0].experimental is True


def test_non_object_nodes_skipped() -> None:
    violations = axe_violations_from_list(
        [{"id": "x", "impact": "moderate", "tags": [], "nodes": ["junk", None, 42]}]
    )
    # All node entries are skipped; the violation still surfaces.
    assert violations[0].nodes == ()
