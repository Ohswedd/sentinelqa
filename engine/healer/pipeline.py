"""Healer facade.

The Healer is invoked by the Analyzer for failures
categorized as ``test_bug``. The facade is a thin orchestrator over
the three repair proposers; it does NOT decide whether a proposal
auto-applies (see :mod:`engine.healer.gating`) and it does NOT write
to disk (see :mod:`engine.healer.writer`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from engine.analyzer.models import AnalyzerResult, FailureSignal
from engine.domain.ids import IdGenerator
from engine.healer.fixture_repair import (
    FixtureRepairInputs,
    propose_fixture_repair,
)
from engine.healer.locator_repair import (
    DomCandidate,
    LocatorRepairInputs,
    propose_locator_repair,
)
from engine.healer.models import LocatorDescriptor, RepairProposal
from engine.healer.wait_repair import WaitRepairInputs, propose_wait_repair


@dataclass(frozen=True)
class HealerInputs:
    """Per-failure inputs the Healer needs.

    The Analyzer assembles this from its own :class:`FailureSignal`
    and any extra context the runner persisted (descriptor snapshot,
    DOM candidates, fixture failure kind).
    """

    test_path: Path
    test_source: str

    locator_line: int | None = None
    descriptor: LocatorDescriptor | None = None
    dom_candidates: Sequence[DomCandidate] = field(default_factory=tuple)

    wait_line: int | None = None

    fixture_call_line: int | None = None
    fixture_failure_kind: str | None = None
    fixture_seed_command: str = "pnpm seed"
    fixture_expected_fields: tuple[str, ...] = field(default_factory=tuple)
    fixture_actual_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealerContext:
    """Per-run configuration for the Healer."""

    auto_apply_threshold: float = 0.9


@dataclass
class Healer:
    """Top-level deterministic Healer.

    The facade does not own state; each ``propose`` call is independent.
    """

    id_generator: IdGenerator | None = None

    def propose(
        self,
        failure: FailureSignal | AnalyzerResult,
        inputs: HealerInputs,
        *,
        context: HealerContext | None = None,
    ) -> tuple[RepairProposal, ...]:
        """Return every applicable proposal for one failure.

        The Healer only runs when the Analyzer categorized the failure
        as ``test_bug`` — callers (Analyzer pipeline) enforce that.
        For ergonomic use the facade accepts either a raw
        :class:`FailureSignal` or a wrapped :class:`AnalyzerResult`.
        """

        ctx = context or HealerContext()
        gen = self.id_generator or IdGenerator()
        proposals: list[RepairProposal] = []

        if (
            inputs.locator_line is not None
            and inputs.descriptor is not None
            and inputs.dom_candidates
        ):
            locator_inputs = LocatorRepairInputs(
                test_path=inputs.test_path,
                test_source=inputs.test_source,
                locator_line=inputs.locator_line,
                descriptor=inputs.descriptor,
                dom_candidates=tuple(inputs.dom_candidates),
            )
            locator_proposal = propose_locator_repair(
                locator_inputs,
                id_generator=gen,
                auto_apply_threshold=ctx.auto_apply_threshold,
            )
            if locator_proposal is not None:
                proposals.append(locator_proposal)

        if inputs.wait_line is not None:
            wait_inputs = WaitRepairInputs(
                test_path=inputs.test_path,
                test_source=inputs.test_source,
                wait_line=inputs.wait_line,
            )
            wait_proposal = propose_wait_repair(
                wait_inputs,
                id_generator=gen,
                auto_apply_threshold=ctx.auto_apply_threshold,
            )
            if wait_proposal is not None:
                proposals.append(wait_proposal)

        if inputs.fixture_call_line is not None and inputs.fixture_failure_kind in {
            "missing_entity",
            "contract_drift",
        }:
            fixture_inputs = FixtureRepairInputs(
                test_path=inputs.test_path,
                test_source=inputs.test_source,
                fixture_call_line=inputs.fixture_call_line,
                failure_kind=inputs.fixture_failure_kind,  # type: ignore[arg-type]
                seed_command=inputs.fixture_seed_command,
                expected_fields=inputs.fixture_expected_fields,
                actual_fields=inputs.fixture_actual_fields,
            )
            proposals.append(propose_fixture_repair(fixture_inputs, id_generator=gen))

        # Deterministic ordering for goldens / re-runs.
        proposals.sort(key=lambda p: (p.kind, p.id))
        return tuple(proposals)


__all__ = ["Healer", "HealerContext", "HealerInputs"]
