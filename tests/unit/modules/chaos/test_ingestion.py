"""chaos JSONL ingestion unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.chaos.ingestion import (
    ChaosIngestError,
    group_by_scenario,
    parse_events,
    read_event_file,
    reports_by_category,
)


def _event(**overrides) -> dict:
    base = {
        "scenario_id": "network.api_500",
        "category": "network",
        "flow": "checkout",
        "observation": "handled_gracefully",
    }
    base.update(overrides)
    return base


def test_parse_events_tolerates_blank_lines() -> None:
    payload = "\n" + json.dumps(_event()) + "\n\n"
    events = parse_events(payload)
    assert len(events) == 1


def test_parse_events_rejects_invalid_json() -> None:
    with pytest.raises(ChaosIngestError, match="invalid JSON"):
        parse_events("{not json}\n")


def test_parse_events_rejects_non_object_top_level() -> None:
    with pytest.raises(ChaosIngestError, match="JSON object"):
        parse_events("[1, 2, 3]\n")


def test_parse_events_rejects_unknown_category() -> None:
    with pytest.raises(ChaosIngestError, match="unknown category"):
        parse_events(json.dumps(_event(category="bogus")) + "\n")


def test_parse_events_rejects_malformed_event_via_pydantic() -> None:
    payload = json.dumps(
        {
            "scenario_id": "",
            "category": "network",
            "flow": "checkout",
            "observation": "handled_gracefully",
        }
    )
    with pytest.raises(ChaosIngestError):
        parse_events(payload + "\n")


def test_read_event_file_returns_empty_when_missing(tmp_path: Path) -> None:
    assert read_event_file(tmp_path / "nope.jsonl") == ()


def test_read_event_file_rejects_oversize(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    # Write a file larger than 8 MiB so the size check trips before parsing.
    chunk = "x" * 1024  # 1 KiB
    with path.open("w", encoding="utf-8") as fh:
        for _ in range(9 * 1024):  # ~9 MiB
            fh.write(chunk)
    with pytest.raises(ChaosIngestError, match="too large"):
        read_event_file(path)


def test_read_event_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_event()) + "\n")
    events = read_event_file(path)
    assert events[0].scenario_id == "network.api_500"


def test_group_by_scenario_collapses_into_results() -> None:
    events = parse_events(
        "\n".join(
            [
                json.dumps(_event(observation="no_error_state")),
                json.dumps(_event(observation="handled_gracefully")),
                json.dumps(_event(scenario_id="ux.duplicate_submit", category="ux", flow="x")),
            ]
        )
        + "\n"
    )
    results = group_by_scenario(events)
    assert {r.scenario_id for r in results} == {
        "network.api_500",
        "ux.duplicate_submit",
    }
    primary = next(r for r in results if r.scenario_id == "network.api_500")
    assert len(primary.events) == 2
    assert len(primary.bad_events) == 1


def test_group_by_scenario_falls_back_to_event_category_for_unknown_id() -> None:
    events = parse_events(
        json.dumps(_event(scenario_id="ux.totally_made_up", category="ux", flow="x")) + "\n"
    )
    results = group_by_scenario(events)
    assert results[0].category == "ux"


def test_reports_by_category_skips_empty_categories() -> None:
    events = parse_events(json.dumps(_event(observation="no_error_state")) + "\n")
    results = group_by_scenario(events)
    reports = reports_by_category(results)
    assert {r.category for r in reports} == {"network"}
