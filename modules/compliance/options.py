"""Per-run options for :class:`modules.compliance.ComplianceModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ComplianceModuleOptions:
    """Inputs the orchestrator threads into the module via ``ctx.options``.

    ``enabled_checks`` controls which sub-checks the module runs. Empty
    tuple means *all enabled-in-config*; the compliance-pack DSL fills
    this in with the pack's check list (``gdpr_baseline``,
    ``ccpa_baseline``, ``soc2_trail``, …).

    ``signals_root`` defaults to ``<run-dir>/compliance/signals/`` —
    the discovery / runner phases may write GDPR / CCPA signals there
    via the TS runtime. Tests inject the path directly.
    """

    enabled_checks: tuple[str, ...] = ()
    signals_root: Path | None = None
    audit_log_path: Path | None = None
    """When set, overrides the default ``<run-dir>/audit.log`` lookup
    for the SOC 2 trail gate. Useful for tests; production reads the
    run's own audit log."""

    flag_missing_consent_banner: bool = False
    enforce_ccpa_link_presence: bool = True
    require_llm_events: bool = False
    require_vault_events: bool = False
    expected_modules: tuple[str, ...] = ()
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["ComplianceModuleOptions"]
