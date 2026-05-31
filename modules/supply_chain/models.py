"""Wire-format models for :class:`modules.supply_chain.SupplyChainModule`.

Mirrors the on-disk shapes the module writes under ``<run-dir>/sbom/``
and ``<run-dir>/supply_chain/``. The schema version is bumped under an
ADR (CLAUDE §34) and is enforced at parse time. Phase 33 / ADR-0045
owns version ``"1"``.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from engine.domain.base import SentinelModel
from engine.domain.finding import Severity
from pydantic import Field, field_validator

SUPPLY_CHAIN_SCHEMA_VERSION: str = "1"
"""Bump under an ADR (CLAUDE §34). Owned by Phase 33."""


# Lockfile ecosystems we understand. CycloneDX 1.5 expects ``purl``
# scheme prefixes that match these names verbatim — keep the strings
# stable.
Ecosystem = Literal[
    "PyPI",
    "npm",
]


LockfileKind = Literal[
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements.txt",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
]
"""The seven lockfile shapes Phase 33 parses (Phase 33 README)."""


class SbomComponent(SentinelModel):
    """One resolved dependency in an SBOM.

    Phase 33 only emits typed components for the lockfiles it parses; we
    intentionally avoid carrying through every optional CycloneDX field
    (hash digests, supplier metadata, vulnerability annotations) so the
    wire shape stays small and our schema-drift guard catches any future
    accidental field additions.
    """

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    name: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=128)
    ecosystem: Ecosystem
    purl: str = Field(min_length=1, max_length=1024)
    licenses: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    direct: bool = False
    """``True`` if the component is a direct dep of the project (vs. transitive)."""

    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)

    @field_validator("purl")
    @classmethod
    def _purl_prefix(cls, value: str) -> str:
        if not value.startswith("pkg:"):
            raise ValueError("SbomComponent.purl must start with 'pkg:' (Package URL spec).")
        return value


class SbomLockfileResult(SentinelModel):
    """Per-lockfile parse outcome — present even when parsing failed."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    path: str = Field(min_length=1, max_length=2048)
    """Relative path to the lockfile from the project root (POSIX-flavour)."""

    kind: LockfileKind
    ecosystem: Ecosystem
    components: tuple[SbomComponent, ...] = Field(default_factory=tuple)
    cyclonedx_path: str | None = Field(default=None, max_length=2048)
    """Relative path to the per-lockfile CycloneDX JSON output, if written."""

    parse_error: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class SbomDocument(SentinelModel):
    """Top-level SBOM index written to ``sbom/index.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    generated_at: datetime
    project_name: str = Field(min_length=1, max_length=200)
    lockfiles: tuple[SbomLockfileResult, ...] = Field(default_factory=tuple)
    components_count: int = Field(default=0, ge=0)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# OSV
# ---------------------------------------------------------------------------


class OsvAdvisory(SentinelModel):
    """One advisory the OSV API returned for a queried component."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    id: str = Field(min_length=1, max_length=128)
    severity: Severity
    """Mapped from OSV's CVSS score (see :func:`modules.supply_chain.osv.severity_from_cvss`)."""

    cwe_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    fixed_in: str | None = Field(default=None, max_length=128)
    summary: str = Field(default="", max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class OsvComponentResult(SentinelModel):
    """Vulnerabilities found for a single component."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    package: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=128)
    ecosystem: Ecosystem
    advisories: tuple[OsvAdvisory, ...] = Field(default_factory=tuple)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class OsvReport(SentinelModel):
    """Top-level OSV result written to ``supply_chain/vulnerabilities.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    queried_at: datetime
    components_count: int = Field(default=0, ge=0)
    vulnerabilities: tuple[OsvComponentResult, ...] = Field(default_factory=tuple)
    skipped: bool = False
    skipped_reason: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


class FreshnessLockfileResult(SentinelModel):
    """Freshness + manifest-drift verdict for one lockfile."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    path: str = Field(min_length=1, max_length=2048)
    kind: LockfileKind
    age_days: int = Field(ge=0)
    stale: bool = False
    threshold_days: int = Field(ge=1)
    manifest_drift: tuple[str, ...] = Field(default_factory=tuple, max_length=256)
    """Each entry is a free-form description of one drifted package."""

    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class FreshnessReport(SentinelModel):
    """Top-level freshness result written to ``supply_chain/freshness.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    checked_at: datetime
    threshold_days: int = Field(ge=1)
    lockfiles: tuple[FreshnessLockfileResult, ...] = Field(default_factory=tuple)
    skipped: bool = False
    skipped_reason: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Postinstall
# ---------------------------------------------------------------------------


PostinstallEcosystem = Literal["npm", "python"]


class PostinstallIssue(SentinelModel):
    """One suspicious postinstall hook."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    ecosystem: PostinstallEcosystem
    package: str = Field(min_length=1, max_length=512)
    path: str = Field(min_length=1, max_length=2048)
    hook: str = Field(min_length=1, max_length=64)
    """For npm: ``preinstall`` / ``install`` / ``postinstall`` / ``prepublishOnly``.

    For Python: ``setup.py`` / ``setup.cfg`` / ``pyproject.toml``.
    """

    snippet: str = Field(min_length=1, max_length=4000)
    pattern: str = Field(min_length=1, max_length=128)
    """The matched pattern (e.g. ``curl``, ``os.system``)."""

    severity: Severity
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class PostinstallReport(SentinelModel):
    """Top-level postinstall result written to ``supply_chain/postinstall_findings.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    scanned_packages: int = Field(default=0, ge=0)
    issues: tuple[PostinstallIssue, ...] = Field(default_factory=tuple)
    skipped: bool = False
    skipped_reason: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


ContainerScanner = Literal["trivy", "grype", "none"]


class ContainerVulnerability(SentinelModel):
    """One CVE found in a container layer."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    scanner: ContainerScanner
    """Which adapter produced this finding."""

    vuln_id: str = Field(min_length=1, max_length=128)
    package: str = Field(min_length=1, max_length=512)
    installed_version: str = Field(min_length=1, max_length=128)
    fixed_version: str | None = Field(default=None, max_length=128)
    severity: Severity
    cwe_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    title: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=4000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class ContainerReport(SentinelModel):
    """Top-level container scanner result written to ``supply_chain/container.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    image: str | None = Field(default=None, max_length=512)
    scanner: ContainerScanner
    findings: tuple[ContainerVulnerability, ...] = Field(default_factory=tuple)
    cap_reached: bool = False
    skipped: bool = False
    skipped_reason: str | None = Field(default=None, max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# License audit
# ---------------------------------------------------------------------------


LicenseVerdict = Literal["allow", "deny", "unknown"]


class LicenseEntry(SentinelModel):
    """License verdict for a single component."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    name: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=128)
    ecosystem: Ecosystem
    spdx_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    verdict: LicenseVerdict
    recommendation: str = Field(default="", max_length=2000)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


class LicenseReport(SentinelModel):
    """Top-level license result written to ``supply_chain/licenses.json``."""

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    allow: tuple[str, ...] = Field(default_factory=tuple)
    deny: tuple[str, ...] = Field(default_factory=tuple)
    unknown_severity: Severity
    entries: tuple[LicenseEntry, ...] = Field(default_factory=tuple)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# Run outcome
# ---------------------------------------------------------------------------


class SupplyChainRunOutcome(SentinelModel):
    """Aggregate result the module persists for the run.

    Each section is optional so the run can record partial progress
    (e.g. SBOM ran, OSV was skipped offline).
    """

    SCHEMA_VERSION: ClassVar[str] = SUPPLY_CHAIN_SCHEMA_VERSION

    sbom: SbomDocument | None = None
    osv: OsvReport | None = None
    freshness: FreshnessReport | None = None
    postinstall: PostinstallReport | None = None
    container: ContainerReport | None = None
    licenses: LicenseReport | None = None
    duration_ms: int = Field(default=0, ge=0)
    incomplete: bool = False
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION)


__all__ = [
    "SUPPLY_CHAIN_SCHEMA_VERSION",
    "ContainerReport",
    "ContainerScanner",
    "ContainerVulnerability",
    "Ecosystem",
    "FreshnessLockfileResult",
    "FreshnessReport",
    "LicenseEntry",
    "LicenseReport",
    "LicenseVerdict",
    "LockfileKind",
    "OsvAdvisory",
    "OsvComponentResult",
    "OsvReport",
    "PostinstallEcosystem",
    "PostinstallIssue",
    "PostinstallReport",
    "SbomComponent",
    "SbomDocument",
    "SbomLockfileResult",
    "SupplyChainRunOutcome",
]
