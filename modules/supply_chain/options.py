"""Per-run options for :class:`modules.supply_chain.SupplyChainModule`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SupplyChainModuleOptions:
    """Inputs the orchestrator threads into the module via ``ctx.options``.

    The CLI sets these from ``--project-root``, ``--sbom``, and the
    per-check ``--no-osv`` / ``--no-container`` flags. When the SDK or
    a direct lifecycle caller provides nothing, the module falls back
    to :class:`engine.config.schema.SupplyChainConfig`.
    """

    project_root: Path | None = None
    sbom_input_path: Path | None = None
    """When set, skip SBOM generation and reuse the SBOM at this path."""

    enabled_checks: tuple[str, ...] = ()
    """Override ``config.policy.supply_chain.enabled_checks`` when non-empty."""

    container_image: str | None = None
    extra_env: Mapping[str, str] = field(default_factory=dict)


__all__ = ["SupplyChainModuleOptions"]
