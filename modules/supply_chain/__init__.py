"""Supply-Chain & Dependency Audit module (, the documentation.3, ADR-0045).

Importing this package wires :class:`SupplyChainModule` into the default
orchestrator registry so ``sentinel supply-chain`` and ``sentinel audit``
both pick it up automatically.

Capabilities ( README):

- CycloneDX 1.5 SBOM generation for 7 lockfile shapes.
- OSV vulnerability lookup with graceful offline degradation.
- Lockfile freshness + manifest drift detection.
- Postinstall hook scanner (npm + Python setup.py AST scan).
- Container image scanner adapter (Trivy / Grype) — optional.
- SPDX license audit with allow / deny / unknown policy.

All checks are defensive / read-only (our engineering rules + §26). The OSV
adapter respects ``policy.supply_chain.osv.rate_limit_rps`` and degrades
to ``skipped`` (not ``passed``) when the API is unreachable. The
container scanner only ever runs against ``policy.supply_chain.container.image``;
it never pulls, never iterates a registry, never scans random images.
"""

from __future__ import annotations

from modules.supply_chain.module import (
    SupplyChainModule,
    SupplyChainModuleOptions,
    register_with_default_registry,
)
from modules.supply_chain.rules import register_supply_chain_rules

# Register SARIF descriptors as an import side-effect, mirroring
# :mod:`modules.security` (, ADR-0018).
register_supply_chain_rules()
register_with_default_registry()


__all__ = [
    "SupplyChainModule",
    "SupplyChainModuleOptions",
    "register_with_default_registry",
]
