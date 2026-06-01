"""Compliance-pack DSL loader.

A *compliance pack* is a strict YAML document that composes existing
SentinelQA modules + checks under a single regime label (WCAG 2.2 AA,
GDPR baseline, CCPA baseline, SOC 2 trail). The loader validates a
pack against a known-modules / known-checks registry **at load time**
so misspelled references fail loudly instead of silently running
nothing.

Pack shape::

 pack:
 id: wcag-2.2-aa
 label: WCAG 2.2 AA (automated)
 description:...
 version: 1
 includes:
 - module: accessibility
 options:
 axe_tags: [wcag2a, wcag2aa, wcag22a, wcag22aa]
 - module: compliance
 checks: [wcag22]
 fail_on:
 - severity: critical
 - severity: high
 warn_on:
 - severity: medium

CLAUDE §28 / wording rule: pack metadata may say "WCAG 2.2 AA
(automated)" but never "WCAG 2.2 compliant". The forbidden-
phrase guard at ``tests/security/test_no_compliance_claims.py``
enforces this for the YAML files under ``policy/compliance/``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Known-module / known-check registries
# ---------------------------------------------------------------------------

Severity = Literal["critical", "high", "medium", "low", "info"]


_KNOWN_CHECKS: dict[str, frozenset[str]] = {
    # Compliance module ships four sub-checks.
    "compliance": frozenset({"gdpr", "ccpa", "soc2_trail", "wcag22"}),
    # Accessibility module's check filter only meaningfully applies to
    # axe tag-set selection today; the per-rule filter is left for
    # future work. The pack DSL accepts an empty checks tuple for
    # accessibility entries (operators tune via ``options.axe_tags``).
    "accessibility": frozenset(),
    # Security / supply_chain / api support module-wide options today,
    # not check-level filtering. Pack entries that include them MUST
    # omit ``checks`` (the loader enforces this).
    "security": frozenset(),
    "supply_chain": frozenset(),
    "api": frozenset(),
    "performance": frozenset(),
    "visual": frozenset(),
    "functional": frozenset(),
    "chaos": frozenset(),
    "llm_audit": frozenset(),
}


def known_modules() -> tuple[str, ...]:
    return tuple(sorted(_KNOWN_CHECKS.keys()))


def known_checks(module: str) -> frozenset[str]:
    return _KNOWN_CHECKS.get(module, frozenset())


# ---------------------------------------------------------------------------
# Pydantic models — strict (unknown keys rejected)
# ---------------------------------------------------------------------------


class _SeverityRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity


class PackInclude(BaseModel):
    """One ``includes:`` entry in a compliance pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module: str = Field(min_length=1, max_length=64)
    options: Mapping[str, Any] = Field(default_factory=dict)
    checks: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("module")
    @classmethod
    def _module_known(cls, value: str) -> str:
        if value not in _KNOWN_CHECKS:
            raise ValueError(
                f"pack.includes[].module {value!r} is not a known SentinelQA module. "
                f"Known modules: {', '.join(known_modules())}."
            )
        return value


class CompliancePack(BaseModel):
    """A loaded compliance pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9.-]*$")
    label: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2_000)
    version: int = Field(default=1, ge=1, le=1_000)
    includes: tuple[PackInclude, ...] = Field(default_factory=tuple, max_length=64)
    fail_on: tuple[_SeverityRule, ...] = Field(default_factory=tuple, max_length=10)
    warn_on: tuple[_SeverityRule, ...] = Field(default_factory=tuple, max_length=10)

    @field_validator("includes")
    @classmethod
    def _checks_known_or_module_allows_empty(
        cls, value: tuple[PackInclude, ...]
    ) -> tuple[PackInclude, ...]:
        for entry in value:
            if not entry.checks:
                continue
            known = _KNOWN_CHECKS.get(entry.module, frozenset())
            if not known:
                raise ValueError(
                    f"pack.includes[].module {entry.module!r} does not support "
                    "the ``checks`` filter; remove the field or split the entry."
                )
            unknown = sorted(set(entry.checks) - known)
            if unknown:
                raise ValueError(
                    f"pack.includes[].module {entry.module!r} has unknown checks: "
                    f"{', '.join(unknown)}. Known checks: {', '.join(sorted(known))}."
                )
        return value

    # ------------------------------------------------------------------
    # Derived views
    # ------------------------------------------------------------------

    def requested_modules(self) -> tuple[str, ...]:
        """Distinct modules the pack wants to run, in declaration order."""

        seen: list[str] = []
        for entry in self.includes:
            if entry.module not in seen:
                seen.append(entry.module)
        return tuple(seen)

    def module_options(self) -> dict[str, dict[str, Any]]:
        """Merge every ``includes[].options`` per module.

        Later includes win on key collisions. ``enabled_checks`` is
        derived from every entry's ``checks`` field (union).
        """

        merged: dict[str, dict[str, Any]] = {}
        check_acc: dict[str, list[str]] = {}
        for entry in self.includes:
            target = merged.setdefault(entry.module, {})
            for key, value in entry.options.items():
                target[key] = value
            if entry.checks:
                bucket = check_acc.setdefault(entry.module, [])
                for check in entry.checks:
                    if check not in bucket:
                        bucket.append(check)
        for module, checks in check_acc.items():
            merged[module]["enabled_checks"] = tuple(checks)
        return merged

    def fail_severities(self) -> tuple[Severity, ...]:
        return tuple(rule.severity for rule in self.fail_on)

    def warn_severities(self) -> tuple[Severity, ...]:
        return tuple(rule.severity for rule in self.warn_on)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class CompliancePackError(ValueError):
    """Raised when a pack fails to load."""


_BUILTIN_PACK_DIR = Path(__file__).resolve().parents[2] / "policy" / "compliance"


def builtin_pack_dir() -> Path:
    return _BUILTIN_PACK_DIR


def load_compliance_pack(source: str | Path) -> CompliancePack:
    """Load a pack from a built-in id, an absolute path, or a relative path.

    Resolution order when ``source`` is a string:

    1. Treat as a built-in pack id (e.g. ``"wcag-2.2-aa"``) and look up
    ``policy/compliance/<id>.yaml`` next to the repository root.
    2. Treat as a filesystem path.

    Always returns a fully-validated :class:`CompliancePack` or raises
    :class:`CompliancePackError`.
    """

    path = _resolve_pack_path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompliancePackError(
            f"compliance pack not readable at {path}: {exc.strerror}"
        ) from exc
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CompliancePackError(f"compliance pack {path} is not valid YAML: {exc}") from exc
    if not isinstance(payload, dict) or "pack" not in payload:
        raise CompliancePackError(
            f"compliance pack {path} must contain a top-level 'pack:' mapping."
        )
    pack_payload = payload["pack"]
    if not isinstance(pack_payload, dict):
        raise CompliancePackError(f"compliance pack {path}: 'pack:' must be a mapping.")
    try:
        return CompliancePack.model_validate(pack_payload)
    except Exception as exc:
        raise CompliancePackError(f"compliance pack {path} failed validation: {exc}") from exc


def _resolve_pack_path(source: str | Path) -> Path:
    if isinstance(source, Path):
        return source
    candidate = Path(source)
    if candidate.exists():
        return candidate
    # Treat as built-in pack id.
    candidate = _BUILTIN_PACK_DIR / f"{source}.yaml"
    if candidate.exists():
        return candidate
    raise CompliancePackError(
        f"compliance pack {source!r} not found. Looked for {source!r} as a path "
        f"and as {candidate}."
    )


__all__ = [
    "CompliancePack",
    "CompliancePackError",
    "PackInclude",
    "builtin_pack_dir",
    "known_checks",
    "known_modules",
    "load_compliance_pack",
]
