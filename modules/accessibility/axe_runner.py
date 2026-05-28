"""Normalise raw ``axe.run`` JSON output into typed :class:`AxeViolation` records.

The TS subcommand serialises axe-core's native shape verbatim. This
module exposes the Python-side validator + typed accessor so unit
tests can exercise the translation against a fixture without invoking
Playwright. The deterministic mapping is also reused in the integration
tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from modules.accessibility.models import AxeImpact, AxeNode, AxeViolation

VALID_IMPACTS: frozenset[str] = frozenset({"critical", "serious", "moderate", "minor"})


def axe_violations_from_payload(payload: Mapping[str, Any]) -> tuple[AxeViolation, ...]:
    """Translate one ``axe.run`` JSON payload to typed violations.

    Accepts either the full ``axe.run`` envelope (``{"violations": [...]}``)
    or a bare list of violation dicts under the ``violations`` key.
    """

    raw = payload.get("violations") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        return ()
    return _normalise(raw)


def axe_violations_from_list(raw: Iterable[Any]) -> tuple[AxeViolation, ...]:
    """Translate a bare iterable of violation dicts to typed violations."""

    return _normalise(list(raw))


def _normalise(raw: list[Any]) -> tuple[AxeViolation, ...]:
    out: list[AxeViolation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rule_id = str(entry.get("id") or entry.get("rule_id") or "").strip()
        if not rule_id:
            continue
        impact_raw = str(entry.get("impact") or "moderate")
        if impact_raw not in VALID_IMPACTS:
            impact_raw = "moderate"
        impact: AxeImpact = impact_raw  # type: ignore[assignment]
        tags_raw = entry.get("tags") or ()
        tags = tuple(str(t) for t in tags_raw if isinstance(t, str))
        nodes = _normalise_nodes(entry.get("nodes") or ())
        out.append(
            AxeViolation(
                rule_id=rule_id,
                impact=impact,
                help=str(entry.get("help") or ""),
                help_url=str(entry.get("helpUrl") or entry.get("help_url") or ""),
                description=str(entry.get("description") or ""),
                tags=tags,
                nodes=nodes,
                experimental="experimental" in tags,
            )
        )
    return tuple(out)


def _normalise_nodes(raw: Iterable[Any]) -> tuple[AxeNode, ...]:
    out: list[AxeNode] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        target_raw = entry.get("target") or ()
        target_list: tuple[str, ...]
        if isinstance(target_raw, str):
            target_list = (target_raw,)
        else:
            target_list = tuple(str(t) for t in target_raw if isinstance(t, str))
        out.append(
            AxeNode(
                target=target_list,
                html=str(entry.get("html") or ""),
                failure_summary=str(entry.get("failureSummary") or ""),
            )
        )
    return tuple(out)


__all__ = [
    "VALID_IMPACTS",
    "axe_violations_from_list",
    "axe_violations_from_payload",
]
