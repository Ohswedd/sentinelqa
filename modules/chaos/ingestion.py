"""Parse JSONL chaos events emitted by the TS chaos helpers.

The TS helpers (``packages/ts-runtime/src/chaos/*``) append one JSON
object per line to ``<run-dir>/chaos/events.jsonl``. This module
parses that file (or any operator-supplied path) into typed
:class:`ChaosScenarioResult` rolls-up grouped by category.

Safety / robustness:

- Every line is parsed through Pydantic so a malformed event raises
 :class:`ChaosIngestError` rather than silently corrupting the run
 (our engineering rules: typed errors).
- The reader caps the file size at 8 MiB to keep a runaway TS helper
 from filling memory; over-cap reads raise :class:`ChaosIngestError`.
- Unknown ``scenario_id`` values are tolerated only for known
 categories — a category outside the canonical catalog is a hard
 error so the audit log preserves what was thrown out.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from modules.chaos.models import (
    ChaosCategory,
    ChaosCategoryReport,
    ChaosEvent,
    ChaosScenarioResult,
)
from modules.chaos.scenarios import CATALOG_BY_ID

_MAX_EVENT_FILE_BYTES: Final[int] = 8 * 1024 * 1024  # 8 MiB
_KNOWN_CATEGORIES: Final[frozenset[ChaosCategory]] = frozenset({"network", "session", "ux", "data"})


class ChaosIngestError(ValueError):
    """Raised when an event payload cannot be parsed.

    The message includes the line number when known so an operator can
    jump straight to the bad row.
    """


def parse_events(payload: str) -> tuple[ChaosEvent, ...]:
    """Parse a JSONL ``payload`` into typed :class:`ChaosEvent` records.

    Blank lines are tolerated (Playwright reporters frequently emit
    trailing newlines). Every non-blank line must be a valid event.
    """

    events: list[ChaosEvent] = []
    for line_no, raw in enumerate(payload.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChaosIngestError(
                f"chaos event line {line_no}: invalid JSON ({exc.msg})."
            ) from exc
        if not isinstance(data, dict):
            raise ChaosIngestError(
                f"chaos event line {line_no}: expected JSON object, got {type(data).__name__}."
            )
        category = data.get("category")
        if category not in _KNOWN_CATEGORIES:
            raise ChaosIngestError(f"chaos event line {line_no}: unknown category {category!r}.")
        try:
            event = ChaosEvent.model_validate(data)
        except ValidationError as exc:
            raise ChaosIngestError(f"chaos event line {line_no}: {exc.errors()[0]['msg']}") from exc
        events.append(event)
    return tuple(events)


def read_event_file(path: Path) -> tuple[ChaosEvent, ...]:
    """Read and parse a JSONL event file.

    Returns an empty tuple when the file is missing — the module then
    reports each requested scenario as ``skipped`` with reason "no
    events produced", so callers can distinguish "events file absent"
    from "events file empty" via the reason text.
    """

    if not path.exists():
        return ()
    size = path.stat().st_size
    if size > _MAX_EVENT_FILE_BYTES:
        raise ChaosIngestError(
            f"chaos event file {path} too large ({size} bytes > {_MAX_EVENT_FILE_BYTES})."
        )
    return parse_events(path.read_text(encoding="utf-8"))


def group_by_scenario(events: tuple[ChaosEvent, ...]) -> tuple[ChaosScenarioResult, ...]:
    """Group events by ``(scenario_id, flow)`` into scenario results.

    Skipping isn't expressible in raw events — that's the orchestrator's
    job. Here we just collapse events into deterministic results.
    """

    buckets: dict[tuple[str, str], list[ChaosEvent]] = defaultdict(list)
    for event in events:
        buckets[(event.scenario_id, event.flow)].append(event)

    results: list[ChaosScenarioResult] = []
    for (scenario_id, flow), bucket in buckets.items():
        catalog_entry = CATALOG_BY_ID.get(scenario_id)
        category: ChaosCategory = (
            catalog_entry.category if catalog_entry is not None else bucket[0].category
        )
        results.append(
            ChaosScenarioResult(
                scenario_id=scenario_id,
                category=category,
                flow=flow,
                events=tuple(bucket),
            )
        )
    results.sort(key=lambda r: (r.category, r.scenario_id, r.flow))
    return tuple(results)


def reports_by_category(
    results: tuple[ChaosScenarioResult, ...],
) -> tuple[ChaosCategoryReport, ...]:
    """Group :class:`ChaosScenarioResult`s into per-category reports.

    Categories absent from the input are NOT synthesized here — the
    module layer is responsible for inserting category-level skip
    records when an entire category was requested but produced no
    events (so the audit trail preserves "we asked, nothing came
    back").
    """

    buckets: dict[ChaosCategory, list[ChaosScenarioResult]] = defaultdict(list)
    for result in results:
        buckets[result.category].append(result)
    reports: list[ChaosCategoryReport] = []
    for category in ("network", "session", "ux", "data"):
        if category not in buckets:
            continue
        results_for_category = tuple(buckets[category])
        reports.append(
            ChaosCategoryReport(
                category=category,
                results=results_for_category,
            )
        )
    return tuple(reports)


__all__ = [
    "ChaosIngestError",
    "group_by_scenario",
    "parse_events",
    "read_event_file",
    "reports_by_category",
]
