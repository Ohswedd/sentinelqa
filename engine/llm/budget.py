"""Shared per-run cost budget (, ADR-0042).

Every provider that posts to a remote endpoint consults a single
:class:`LlmBudget` instance attached to the run lifecycle. ``pre_check``
guards against expensive calls; ``add`` records the actual cost once the
response is in hand. When the projected cost would breach the budget the
provider raises :class:`engine.errors.LlmBudgetExceededError` and the
caller falls back to the deterministic path.

Historical compatibility: this module is the canonical home for
:class:`LlmUsage`, :func:`estimate_cost_usd`, and the
``ensure_within_budget`` / ``BudgetExceededError`` shapes that lived on
:mod:`engine.planner.llm_adapter` and :mod:`engine.analyzer.llm_explainer`.
Both modules now re-export from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from engine.errors.base import LlmBudgetExceededError

# Per-1k-token prices (USD). Conservative defaults that approximate the
# mid-tier model on each provider. Real providers override these with
# their own table.
_DEFAULT_PRICE_PER_1K_INPUT: float = 0.003
_DEFAULT_PRICE_PER_1K_OUTPUT: float = 0.015


@dataclass(frozen=True, slots=True)
class LlmUsage:
    """Cumulative token + cost usage across one or more LLM calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0

    def add(self, *, input_tokens: int, output_tokens: int, cost_usd: float) -> LlmUsage:
        return LlmUsage(
            input_tokens=self.input_tokens + input_tokens,
            output_tokens=self.output_tokens + output_tokens,
            cost_usd=self.cost_usd + cost_usd,
            requests=self.requests + 1,
        )


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    price_per_1k_input: float = _DEFAULT_PRICE_PER_1K_INPUT,
    price_per_1k_output: float = _DEFAULT_PRICE_PER_1K_OUTPUT,
) -> float:
    """Token-based cost estimate. Both prices are USD per 1k tokens."""

    return (input_tokens / 1000.0) * price_per_1k_input + (
        output_tokens / 1000.0
    ) * price_per_1k_output


# ---------------------------------------------------------------------------
# Backwards-compat alias for the pre-Phase-30 planner/analyzer code.
# Both subclass ``RuntimeError`` historically; the typed Sentinel error
# now extends ``SentinelError`` instead. We keep an exception type that
# satisfies BOTH bases so existing ``except BudgetExceededError`` blocks
# in the planner / analyzer keep catching the same condition.
# ---------------------------------------------------------------------------


class BudgetExceededError(LlmBudgetExceededError, RuntimeError):
    """Historical alias kept for the planner/analyzer call sites.

    Catching :class:`RuntimeError` still works (the original base); the
    new typed lifecycle catches the SentinelError too.
    """


def ensure_within_budget(
    *,
    usage: LlmUsage,
    additional_cost: float,
    budget_usd: float,
) -> None:
    """Raise :class:`BudgetExceededError` if the next request would exceed budget."""

    projected = usage.cost_usd + additional_cost
    if projected > budget_usd:
        raise BudgetExceededError(
            f"LLM cost projected {projected:.4f} USD exceeds budget "
            f"{budget_usd:.4f} USD. Falling back to deterministic-only path.",
            projected_usd=projected,
            budget_usd=budget_usd,
        )


# ---------------------------------------------------------------------------
# Per-run budget aggregator. Lives on the lifecycle context.
# ---------------------------------------------------------------------------


Caller = Literal["planner", "analyzer", "healer", "doctor", "test"]


@dataclass
class LlmBudget:
    """One per-run budget shared across every LLM caller.

    Each caller (planner / analyzer / healer) optionally has its own
    sub-budget; the global ``max_usd_per_run`` is the hard cap. The
    lifecycle creates one of these at run start and hands it to every
    provider via :class:`engine.llm.providers._http_base.HttpLlmProviderBase`.
    """

    max_usd_per_run: float = 0.50
    max_usd_planner: float | None = None
    max_usd_analyzer: float | None = None
    max_usd_healer: float | None = None
    _by_caller: dict[str, LlmUsage] = field(default_factory=dict)

    def usage_for(self, caller: Caller) -> LlmUsage:
        return self._by_caller.get(caller, LlmUsage())

    def total(self) -> LlmUsage:
        out = LlmUsage()
        for usage in self._by_caller.values():
            out = LlmUsage(
                input_tokens=out.input_tokens + usage.input_tokens,
                output_tokens=out.output_tokens + usage.output_tokens,
                cost_usd=out.cost_usd + usage.cost_usd,
                requests=out.requests + usage.requests,
            )
        return out

    def _cap_for(self, caller: Caller) -> float:
        if caller == "planner" and self.max_usd_planner is not None:
            return self.max_usd_planner
        if caller == "analyzer" and self.max_usd_analyzer is not None:
            return self.max_usd_analyzer
        if caller == "healer" and self.max_usd_healer is not None:
            return self.max_usd_healer
        return self.max_usd_run_for(caller)

    def max_usd_run_for(self, caller: Caller) -> float:
        return self.max_usd_per_run

    def pre_check(self, *, caller: Caller, estimated_cost_usd: float) -> None:
        """Raise :class:`LlmBudgetExceededError` if this call would breach
        either the caller sub-budget or the global cap."""

        cap = self._cap_for(caller)
        usage = self._by_caller.get(caller, LlmUsage())
        projected = usage.cost_usd + estimated_cost_usd
        if projected > cap:
            raise LlmBudgetExceededError(
                f"LLM budget for {caller!r} would be exceeded: projected "
                f"{projected:.4f} USD > cap {cap:.4f} USD.",
                projected_usd=projected,
                budget_usd=cap,
            )
        total_projected = self.total().cost_usd + estimated_cost_usd
        if total_projected > self.max_usd_per_run:
            raise LlmBudgetExceededError(
                f"LLM run budget exceeded: projected {total_projected:.4f} "
                f"USD > cap {self.max_usd_per_run:.4f} USD.",
                projected_usd=total_projected,
                budget_usd=self.max_usd_per_run,
            )

    def add(
        self,
        *,
        caller: Caller,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        current = self._by_caller.get(caller, LlmUsage())
        self._by_caller[caller] = current.add(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )


__all__ = [
    "BudgetExceededError",
    "Caller",
    "LlmBudget",
    "LlmUsage",
    "ensure_within_budget",
    "estimate_cost_usd",
]
