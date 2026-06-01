"""SOC 2 audit-trail completeness gate.

Audits the run's own ``audit.log`` against seven gates so a SOC 2
auditor can point at the SentinelQA run artefact as evidence. The
goal is **not** to attest that the target product is SOC 2 compliant
— it is to make SentinelQA's own run admissible.

The seven gates:

1. **Trail exists** — the run wrote at least one ``audit.log`` line.
2. **Trail is JSONL** — every non-empty line parses as a JSON object.
3. **Timestamps monotonic** — entries are append-only (no edits to
 prior lines / no out-of-order timestamps).
4. **Safety decisions recorded** — at least one ``policy_decision`` /
 ``safety`` entry per run.
5. **Module events recorded** — at least one ``module_start`` *and*
 one ``module_end`` entry per module that ran.
6. **Artifact events recorded** — at least one ``artifact_written``
 entry.
7. **No secret leakage** — no cookie / Authorization / Set-Cookie
 *value* present unredacted. Re-uses the secret-leak
 rules — see :data:`SECRET_LEAK_TOKENS`.

Optional gates (only enforced when the pack opts in):

- **LLM events recorded** — at least one ``llm_call`` entry, with
 ``provider`` + ``cost_usd`` fields.
- **Vault events recorded** — at least one ``vault_access`` entry.

If any gate fails, the module emits a single typed finding per gate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.compliance.models import (
    Soc2CheckReport,
    Soc2GateResult,
    Soc2Issue,
)

_AUTO_PREFIX = "Automated SOC 2 trail check found"

_COMPLIANCE_TRAIL_MISSING = "soc2:trail-missing"
_COMPLIANCE_TRAIL_NOT_JSONL = "soc2:trail-not-jsonl"
_COMPLIANCE_TRAIL_MONOTONIC = "soc2:trail-non-monotonic"
_COMPLIANCE_TRAIL_SAFETY = "soc2:trail-missing-safety-decision"
_COMPLIANCE_TRAIL_MODULE = "soc2:trail-missing-module-event"
_COMPLIANCE_TRAIL_ARTIFACT = "soc2:trail-missing-artifact-event"
_COMPLIANCE_TRAIL_LLM = "soc2:trail-missing-llm-event"
_COMPLIANCE_TRAIL_VAULT = "soc2:trail-missing-vault-event"
_COMPLIANCE_TRAIL_SECRET = "soc2:trail-secret-leak"


# Heuristic secret-leak tokens. The redaction layer (see
# ``engine/policy/redaction.py``) replaces matched values with
# ``[REDACTED:<category>]`` markers, so seeing the marker is fine.
# What we flag is *un*redacted look-alikes that should have been
# stripped — long bearer tokens, JWT-shaped strings, Set-Cookie
# header values that carry an actual value.
SECRET_LEAK_TOKENS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{16,}\b"),
    re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Set-Cookie:\s*[^\s;]+=[^\s;]+"),
    re.compile(r'\bAuthorization"\s*:\s*"(?!\[REDACTED)[^"]+"'),
    re.compile(r'\b(?:session|cookie)_value"\s*:\s*"(?!\[REDACTED)[^"]+"'),
)


# ---------------------------------------------------------------------------
# Input shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Soc2TrailInputs:
    """Optional gates configuration.

    Defaults match the strict ``soc2-trail`` pack. The base four (1-3
    + 7) and module/artifact gates are always enforced; LLM and vault
    gates are off unless the pack opts in via ``require_llm_events`` /
    ``require_vault_events``.
    """

    require_llm_events: bool = False
    require_vault_events: bool = False
    expected_modules: tuple[str, ...] = ()
    """When non-empty, every named module must have a matching
    ``module_start`` / ``module_end`` pair."""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TrailParse:
    entries: tuple[dict[str, Any], ...]
    parse_errors: tuple[str, ...]
    raw_lines: tuple[str, ...]


def _parse_trail(path: Path) -> _TrailParse:
    if not path.exists():
        return _TrailParse(entries=(), parse_errors=(), raw_lines=())
    raw = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    raw_lines: list[str] = []
    for idx, line in enumerate(raw, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        raw_lines.append(line)
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            errors.append(f"line {idx}: {exc.msg}")
            continue
        if not isinstance(parsed, dict):
            errors.append(f"line {idx}: not a JSON object")
            continue
        entries.append(parsed)
    return _TrailParse(
        entries=tuple(entries),
        parse_errors=tuple(errors),
        raw_lines=tuple(raw_lines),
    )


# ---------------------------------------------------------------------------
# Gate evaluators
# ---------------------------------------------------------------------------


def _gate_trail_exists(parse: _TrailParse, path: Path) -> Soc2GateResult:
    if not path.exists():
        return Soc2GateResult(
            gate="trail-exists",
            passed=False,
            detail=f"audit.log not found at {path}",
        )
    if not parse.raw_lines:
        return Soc2GateResult(
            gate="trail-exists",
            passed=False,
            detail="audit.log is empty",
        )
    return Soc2GateResult(gate="trail-exists", passed=True)


def _gate_trail_jsonl(parse: _TrailParse) -> Soc2GateResult:
    if parse.parse_errors:
        detail = "; ".join(parse.parse_errors[:5])
        return Soc2GateResult(
            gate="trail-jsonl",
            passed=False,
            detail=f"trail contains non-JSON lines: {detail}",
        )
    return Soc2GateResult(gate="trail-jsonl", passed=True)


def _gate_trail_monotonic(parse: _TrailParse) -> Soc2GateResult:
    last_ts: str | None = None
    for idx, entry in enumerate(parse.entries, start=1):
        ts = entry.get("ts")
        if not isinstance(ts, str):
            continue
        if last_ts is not None and ts < last_ts:
            return Soc2GateResult(
                gate="trail-monotonic",
                passed=False,
                detail=(
                    f"line {idx}: timestamp {ts!r} is earlier than the "
                    f"previous entry ({last_ts!r})"
                ),
            )
        last_ts = ts
    return Soc2GateResult(gate="trail-monotonic", passed=True)


def _entry_kind(entry: dict[str, Any]) -> str:
    for key in ("event", "kind", "type", "category"):
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return ""


def _gate_safety_decisions(parse: _TrailParse) -> Soc2GateResult:
    for entry in parse.entries:
        kind = _entry_kind(entry).lower()
        if "safety" in kind or "policy_decision" in kind or "decision" in kind:
            return Soc2GateResult(gate="trail-safety-decisions", passed=True)
        # Decisions older than use the verb directly.
        if entry.get("decision") in {"allow", "block"}:
            return Soc2GateResult(gate="trail-safety-decisions", passed=True)
    return Soc2GateResult(
        gate="trail-safety-decisions",
        passed=False,
        detail="no policy_decision / safety entry observed",
    )


def _module_events(parse: _TrailParse) -> tuple[set[str], set[str]]:
    starts: set[str] = set()
    ends: set[str] = set()
    for entry in parse.entries:
        kind = _entry_kind(entry).lower()
        module = entry.get("module")
        if not isinstance(module, str):
            continue
        if "module_start" in kind:
            starts.add(module)
        elif "module_end" in kind:
            ends.add(module)
    return starts, ends


def _gate_module_events(parse: _TrailParse, inputs: Soc2TrailInputs) -> Soc2GateResult:
    starts, ends = _module_events(parse)
    if not starts and not ends:
        return Soc2GateResult(
            gate="trail-module-events",
            passed=False,
            detail="no module_start / module_end entries",
        )
    for module in inputs.expected_modules:
        if module not in starts or module not in ends:
            return Soc2GateResult(
                gate="trail-module-events",
                passed=False,
                detail=(
                    f"module {module!r} is missing a start or end event "
                    f"(starts={sorted(starts)}, ends={sorted(ends)})"
                ),
            )
    return Soc2GateResult(gate="trail-module-events", passed=True)


def _gate_artifact_events(parse: _TrailParse) -> Soc2GateResult:
    for entry in parse.entries:
        kind = _entry_kind(entry).lower()
        if "artifact" in kind or entry.get("artifact_path"):
            return Soc2GateResult(gate="trail-artifact-events", passed=True)
    return Soc2GateResult(
        gate="trail-artifact-events",
        passed=False,
        detail="no artifact_written entry observed",
    )


def _gate_llm_events(parse: _TrailParse) -> Soc2GateResult:
    for entry in parse.entries:
        kind = _entry_kind(entry).lower()
        if "llm" in kind and entry.get("provider") and entry.get("cost_usd") is not None:
            return Soc2GateResult(gate="trail-llm-events", passed=True)
    return Soc2GateResult(
        gate="trail-llm-events",
        passed=False,
        detail="no llm_call entry with provider + cost_usd",
    )


def _gate_vault_events(parse: _TrailParse) -> Soc2GateResult:
    for entry in parse.entries:
        kind = _entry_kind(entry).lower()
        if "vault" in kind:
            return Soc2GateResult(gate="trail-vault-events", passed=True)
    return Soc2GateResult(
        gate="trail-vault-events",
        passed=False,
        detail="no vault_access entry observed",
    )


def detect_secret_leaks(raw_lines: Iterable[str]) -> tuple[str, ...]:
    """Return matched secret-leak excerpts (for the failing detail)."""

    hits: list[str] = []
    for line in raw_lines:
        for pattern in SECRET_LEAK_TOKENS:
            match = pattern.search(line)
            if match is not None:
                hits.append(match.group(0))
                break
    return tuple(hits)


def _gate_no_secret_leak(parse: _TrailParse) -> Soc2GateResult:
    leaks = detect_secret_leaks(parse.raw_lines)
    if leaks:
        return Soc2GateResult(
            gate="trail-no-secret-leak",
            passed=False,
            detail=(f"{len(leaks)} secret-shaped substring(s) observed " "unredacted in the trail"),
        )
    return Soc2GateResult(gate="trail-no-secret-leak", passed=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_GATE_TO_CATEGORY: dict[str, str] = {
    "trail-exists": "trail-missing",
    "trail-jsonl": "trail-not-jsonl",
    "trail-monotonic": "trail-non-monotonic",
    "trail-safety-decisions": "trail-missing-safety-decision",
    "trail-module-events": "trail-missing-module-event",
    "trail-artifact-events": "trail-missing-artifact-event",
    "trail-llm-events": "trail-missing-llm-event",
    "trail-vault-events": "trail-missing-vault-event",
    "trail-no-secret-leak": "trail-secret-leak",
}

_GATE_TO_COMPLIANCE_ID: dict[str, str] = {
    "trail-exists": _COMPLIANCE_TRAIL_MISSING,
    "trail-jsonl": _COMPLIANCE_TRAIL_NOT_JSONL,
    "trail-monotonic": _COMPLIANCE_TRAIL_MONOTONIC,
    "trail-safety-decisions": _COMPLIANCE_TRAIL_SAFETY,
    "trail-module-events": _COMPLIANCE_TRAIL_MODULE,
    "trail-artifact-events": _COMPLIANCE_TRAIL_ARTIFACT,
    "trail-llm-events": _COMPLIANCE_TRAIL_LLM,
    "trail-vault-events": _COMPLIANCE_TRAIL_VAULT,
    "trail-no-secret-leak": _COMPLIANCE_TRAIL_SECRET,
}


def audit_soc2_trail(
    trail_path: Path,
    inputs: Soc2TrailInputs | None = None,
) -> Soc2CheckReport:
    """Run every SOC 2 audit-trail gate against ``trail_path``."""

    inputs = inputs or Soc2TrailInputs()
    parse = _parse_trail(trail_path)
    gates: list[Soc2GateResult] = []
    gates.append(_gate_trail_exists(parse, trail_path))
    if gates[-1].passed:
        gates.append(_gate_trail_jsonl(parse))
        gates.append(_gate_trail_monotonic(parse))
        gates.append(_gate_safety_decisions(parse))
        gates.append(_gate_module_events(parse, inputs))
        gates.append(_gate_artifact_events(parse))
        if inputs.require_llm_events:
            gates.append(_gate_llm_events(parse))
        if inputs.require_vault_events:
            gates.append(_gate_vault_events(parse))
        gates.append(_gate_no_secret_leak(parse))
    issues: list[Soc2Issue] = []
    for gate in gates:
        if gate.passed:
            continue
        issues.append(
            Soc2Issue(
                category=_GATE_TO_CATEGORY[gate.gate],  # type: ignore[arg-type]
                description=(f"{_AUTO_PREFIX}: {gate.gate} gate failed — {gate.detail}"),
                compliance_id=_GATE_TO_COMPLIANCE_ID[gate.gate],
            )
        )
    return Soc2CheckReport(
        trail_path=str(trail_path),
        entries_read=len(parse.entries),
        gates=tuple(gates),
        issues=tuple(issues),
    )


__all__ = [
    "SECRET_LEAK_TOKENS",
    "Soc2TrailInputs",
    "audit_soc2_trail",
    "detect_secret_leaks",
]
