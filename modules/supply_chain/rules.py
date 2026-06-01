"""SARIF rule catalog for the supply-chain module (, ADR-0045).

Every finding the module emits carries a stable ``SUP-*`` rule id so
SARIF readers can render help URIs and dashboards can correlate
findings across runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from engine.reporter.sarif_rules import (
    SarifRule,
    SarifRuleRegistry,
    default_sarif_registry,
)

_HELP_BASE: Final[str] = "https://docs.sentinelqa.dev/rules/supply-chain/"


@dataclass(frozen=True, slots=True)
class SupplyChainRule:
    rule_id: str
    category: str
    name: str
    title: str
    description: str
    recommendation: str
    default_severity: str = "warning"

    @property
    def help_uri(self) -> str:
        slug = self.rule_id.lower().replace("_", "-")
        return f"{_HELP_BASE}{slug}"

    def to_sarif_rule(self) -> SarifRule:
        return SarifRule(
            id=self.rule_id,
            name=self.name,
            short_description=self.title,
            full_description=self.description,
            help_uri=self.help_uri,
            category=self.category,
            default_severity=self.default_severity,
        )


_RULES: Final[tuple[SupplyChainRule, ...]] = (
    SupplyChainRule(
        rule_id="SUP-OSV-VULNERABLE-DEP",
        category="supply_chain/osv/vulnerable-dep",
        name="vulnerable-dependency",
        title="A dependency in the SBOM has a known vulnerability (OSV).",
        description=(
            "The OSV database returned at least one advisory for this "
            "component@version. The severity tracks the advisory's CVSS "
            "score; the fix is to upgrade to the advisory's listed fixed "
            "version or replace the dependency."
        ),
        recommendation=(
            "Bump the dependency to the fixed version listed in the advisory, "
            "or — if no fix is available — remove the dependency or contain "
            "its blast radius with a sandbox."
        ),
        default_severity="error",
    ),
    SupplyChainRule(
        rule_id="SUP-FRESH-STALE-LOCKFILE",
        category="supply_chain/freshness/stale-lockfile",
        name="stale-lockfile",
        title="Lockfile is older than the configured freshness threshold.",
        description=(
            "Stale lockfiles often mean upstream security fixes have not "
            "been merged. The threshold is configurable via "
            "policy.supply_chain.max_lockfile_age_days (default 180)."
        ),
        recommendation=(
            "Re-run the package manager's install / lock command and "
            "commit the refreshed lockfile."
        ),
    ),
    SupplyChainRule(
        rule_id="SUP-FRESH-MANIFEST-DRIFT",
        category="supply_chain/freshness/manifest-drift",
        name="manifest-drift",
        title="Lockfile and manifest disagree about direct dependencies.",
        description=(
            "A direct dependency declared in the manifest (package.json / "
            "pyproject.toml) is missing from the corresponding lockfile, "
            "which almost always means install was skipped before the "
            "last commit."
        ),
        recommendation=(
            "Run the package manager's install command (npm i / pnpm i / "
            "uv sync / poetry lock) and commit the regenerated lockfile."
        ),
    ),
    SupplyChainRule(
        rule_id="SUP-POSTINSTALL-NETWORK",
        category="supply_chain/postinstall/network-call",
        name="postinstall-network-call",
        title="A postinstall script calls a network binary (curl / wget / nc).",
        description=(
            "Postinstall scripts that reach to the network during ``npm "
            "install`` are a classic supply-chain attack vector "
            "(CWE-506). Even when benign, they make package installs "
            "non-reproducible."
        ),
        recommendation=(
            "Review the package and either pin to an audited version, "
            "replace it, or run installs with --ignore-scripts and "
            "vendor the build artifacts."
        ),
        default_severity="error",
    ),
    SupplyChainRule(
        rule_id="SUP-POSTINSTALL-FS-WRITE",
        category="supply_chain/postinstall/fs-write",
        name="postinstall-fs-write",
        title="A postinstall script writes outside the package directory.",
        description=(
            "Postinstall scripts that touch /etc, /usr, $HOME, or other "
            "system paths are non-portable and often malicious "
            "(CWE-506)."
        ),
        recommendation=(
            "Review the package; pin or replace it. Run npm with "
            "--ignore-scripts where feasible."
        ),
    ),
    SupplyChainRule(
        rule_id="SUP-POSTINSTALL-PYTHON-EXEC",
        category="supply_chain/postinstall/python-exec",
        name="postinstall-python-exec",
        title="A setup.py imports subprocess / urllib / requests at module top-level.",
        description=(
            "Importing subprocess, socket, or HTTP libraries at the top "
            "of setup.py means the code runs during ``pip install`` — "
            "a documented supply-chain attack pattern (CWE-506)."
        ),
        recommendation=(
            "Pin to an audited version or replace the dependency. "
            "Where possible, install wheels (``--only-binary``) so "
            "setup.py never executes."
        ),
        default_severity="error",
    ),
    SupplyChainRule(
        rule_id="SUP-CONTAINER-CVE",
        category="supply_chain/container/cve",
        name="container-cve",
        title="A CVE was found in the configured container image.",
        description=(
            "The container scanner (Trivy or Grype) reported one or "
            "more CVEs in the configured image. Severity tracks the "
            "advisory; fixed versions are listed when available."
        ),
        recommendation=(
            "Rebuild the image from a patched base, upgrade the affected "
            "package(s), or — if the CVE is unfixable — document the "
            "mitigation in the run config's exception list."
        ),
        default_severity="error",
    ),
    SupplyChainRule(
        rule_id="SUP-CONTAINER-SCANNER-NOT-INSTALLED",
        category="supply_chain/container/scanner-not-installed",
        name="container-scanner-not-installed",
        title="Neither Trivy nor Grype is on PATH.",
        description=(
            "The container check is configured (``policy.supply_chain."
            "container.image`` is set) but no scanner binary is available. "
            "The check is skipped, not failed — install Trivy or Grype to "
            "enable it."
        ),
        recommendation=(
            "Install Trivy (https://aquasecurity.github.io/trivy) or "
            "Grype (https://github.com/anchore/grype). SentinelQA never "
            "auto-installs scanners."
        ),
        default_severity="note",
    ),
    SupplyChainRule(
        rule_id="SUP-LICENSE-DENY",
        category="supply_chain/license/deny",
        name="license-conflict",
        title="A dependency uses a denied SPDX license.",
        description=(
            "The component's declared license appears on the configured "
            "denylist (e.g. AGPL-3.0 in an Apache-2.0 product). This "
            "blocks the run unless the legal team has signed off."
        ),
        recommendation=(
            "Either remove the dependency or update the allowlist with "
            "approval from the legal owner."
        ),
        default_severity="error",
    ),
    SupplyChainRule(
        rule_id="SUP-LICENSE-UNKNOWN",
        category="supply_chain/license/unknown",
        name="license-unknown",
        title="A dependency has no declared SPDX license.",
        description=(
            "Without a declared SPDX id we cannot evaluate the dependency "
            "against the project's allow / deny policy. Often the "
            "license is in the package's LICENSE file but missing from "
            "the lockfile."
        ),
        recommendation=(
            "Verify the license upstream; add it to the allowlist, or " "replace the dependency."
        ),
        default_severity="note",
    ),
)


_REGISTERED: bool = False


def register_supply_chain_rules(
    registry: SarifRuleRegistry | None = None,
) -> None:
    """Register every SUP-* rule with the SARIF registry (idempotent).

    Re-importing :mod:`modules.supply_chain` would otherwise raise on the
    second call since :meth:`SarifRuleRegistry.register` refuses
    duplicates. Idempotency mirrors :func:`modules.security.rules.register_security_rules`.
    """

    global _REGISTERED
    target = registry or default_sarif_registry()
    if target is default_sarif_registry() and _REGISTERED:
        return
    known = set(target.known_categories())
    for rule in _RULES:
        if rule.category in known:
            continue
        target.register(rule.to_sarif_rule())
    if target is default_sarif_registry():
        _REGISTERED = True


def all_rules() -> tuple[SupplyChainRule, ...]:
    return _RULES


__all__ = [
    "SupplyChainRule",
    "all_rules",
    "register_supply_chain_rules",
]
