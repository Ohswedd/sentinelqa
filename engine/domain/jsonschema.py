"""JSON Schema generation for domain models.

Wired into the ``make schemas`` target. Each entity ships its schema as a
separate `*.schema.json` under ``packages/shared-schema/``, so the
TypeScript runtime (Phase 04) and external integrations can validate the
same payloads Python emits without re-implementing the model definitions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.element import Element
from engine.domain.evidence import Evidence
from engine.domain.finding import Finding
from engine.domain.flow import Flow
from engine.domain.form import Form
from engine.domain.module_result import ModuleResult
from engine.domain.policy_decision import PolicyDecision
from engine.domain.project import Project
from engine.domain.quality_score import QualityScore
from engine.domain.repair_suggestion import RepairSuggestion
from engine.domain.risk_map import RiskMap
from engine.domain.route import Route
from engine.domain.target import Target
from engine.domain.test_case import TestCase
from engine.domain.test_plan import TestPlan
from engine.domain.test_run import TestRun

if TYPE_CHECKING:
    from engine.domain.base import SentinelModel

# Every artifact that gets a generated schema file. Ordered so the dump on
# disk is stable across runs (deterministic builds — CLAUDE.md §19).
_MODELS: tuple[type[Any], ...] = (
    Project,
    Target,
    Route,
    Element,
    Form,
    ApiEndpoint,
    Flow,
    TestCase,
    TestPlan,
    TestRun,
    ModuleResult,
    Finding,
    Evidence,
    QualityScore,
    PolicyDecision,
    RepairSuggestion,
    DiscoveryGraph,
    RiskMap,
)


def _model_filename(model: type[Any]) -> str:
    # snake_case the model name: ApiEndpoint -> api_endpoint
    out: list[str] = []
    for i, ch in enumerate(model.__name__):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out) + ".schema.json"


def dump_schemas(out_dir: Path) -> list[Path]:
    """Write one ``*.schema.json`` per domain model into ``out_dir``.

    Returns the list of written paths (sorted, deterministic). ``out_dir``
    is created if missing. Existing files are overwritten.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in _MODELS:
        schema = model.model_json_schema()
        # Annotate with the SentinelQA schema version so downstream
        # consumers can reject mismatched documents without parsing.
        version = getattr(model, "SCHEMA_VERSION", None)
        if version is not None:
            schema = {**schema, "x-sentinelqa-schema-version": version}
        path = out_dir / _model_filename(model)
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    written.sort()
    return written


def all_models() -> tuple[type[SentinelModel], ...]:
    """Return the tuple of domain models that ship a generated schema."""

    return tuple(_MODELS)


__all__ = ["dump_schemas", "all_models"]
