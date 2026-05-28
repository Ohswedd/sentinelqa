"""Pydantic models for ``sentinel.config.yaml`` (PRD §17.1).

Every key in the example YAML in the PRD maps to one of these models. The
loader (`engine.config.loader`) rejects unknown keys (`extra="forbid"`) and
runs the validators below, so malformed configs fail fast at the CLI
boundary with a precise error code (E-CFG-002).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import AnyUrl, Field, field_validator, model_validator

from engine.domain.base import SentinelModel
from engine.domain.project import Framework, PackageManager
from engine.domain.schema import CONFIG_SCHEMA_VERSION
from engine.domain.target import Mode

# ---------------------------------------------------------------------------
# Sub-sections
# ---------------------------------------------------------------------------


class ProjectConfig(SentinelModel):
    """`project:` block."""

    name: str = Field(min_length=1, max_length=200)
    framework: Framework = "unknown"
    package_manager: PackageManager = "unknown"


class SourceConfig(SentinelModel):
    """`source:` block."""

    root: Path = Path(".")
    include: tuple[str, ...] = Field(default_factory=tuple)
    exclude: tuple[str, ...] = Field(default_factory=tuple)


class TargetConfig(SentinelModel):
    """`target:` block."""

    base_url: AnyUrl
    allowed_hosts: tuple[str, ...] = Field(default_factory=tuple)
    proof_of_authorization: Path | None = None

    @field_validator("allowed_hosts")
    @classmethod
    def _reject_wildcards(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for host in value:
            if "*" in host or "?" in host:
                raise ValueError(
                    f"Wildcard host {host!r} is not allowed (CLAUDE.md §6). "
                    "List every authorized host explicitly."
                )
        return value


class AuthConfig(SentinelModel):
    """`auth:` block.

    Secrets are NEVER inlined here — only env-var names are accepted via
    the ``*_env`` keys. The loader enforces this via :class:`ConfigSecretInlineError`.
    """

    strategy: Literal["test_user", "api_key", "oauth", "none"] = "none"
    login_url: str | None = Field(default=None, max_length=2048)
    username_env: str | None = Field(default=None, max_length=128)
    password_env: str | None = Field(default=None, max_length=128)
    token_env: str | None = Field(default=None, max_length=128)


class ModulesConfig(SentinelModel):
    """`modules:` block.

    Booleans only — granular module config lives inside each module's own
    sub-section (PRD §17 lists `security`, `performance`, etc. at the top
    level of the YAML).
    """

    functional: bool = True
    api: bool = True
    accessibility: bool = True
    performance: bool = True
    visual: bool = False
    security: bool = True
    chaos: bool = False
    llm_audit: bool = True


class SecurityConfig(SentinelModel):
    """`security:` block."""

    mode: Mode = "safe"
    destructive_tests: bool = False
    max_requests_per_second: int = Field(default=5, ge=1, le=1000)
    allowed_payload_level: Literal["none", "low", "medium", "high"] = "low"

    @model_validator(mode="after")
    def _destructive_requires_mode(self) -> SecurityConfig:
        if self.destructive_tests and self.mode != "authorized_destructive":
            raise ValueError(
                "security.destructive_tests=true requires "
                "security.mode='authorized_destructive'."
            )
        return self


class PerformanceBudgets(SentinelModel):
    """`performance.budgets:` block."""

    lcp_ms: int = Field(default=2500, ge=0)
    cls: float = Field(default=0.1, ge=0)
    inp_ms: int = Field(default=200, ge=0)
    api_p95_ms: int = Field(default=500, ge=0)
    js_total_kb: int = Field(default=500, ge=0)


class PerformanceConfig(SentinelModel):
    """`performance:` block."""

    budgets: PerformanceBudgets = Field(default_factory=PerformanceBudgets)


class VisualConfig(SentinelModel):
    """`visual:` block."""

    baselines_dir: Path = Path(".sentinel/baselines")
    threshold: float = Field(default=0.02, ge=0.0, le=1.0)
    mask_dynamic_content: bool = True


class DiscoveryOpenAPIConfig(SentinelModel):
    """`discovery.openapi:` block — optional schema augmentation."""

    path: Path | None = None
    url: str | None = Field(default=None, max_length=2048)


class DiscoveryGraphQLConfig(SentinelModel):
    """`discovery.graphql:` block — optional schema augmentation."""

    path: Path | None = None
    url: str | None = Field(default=None, max_length=2048)


class DiscoveryConfig(SentinelModel):
    """`discovery:` block (PRD §9.1, ADR-0010).

    The MVP `engine: "http"` backend is the only one shipped in Phase 05;
    `engine: "playwright"` is reserved for Phase 17 (see
    `plans/phase-17-ci-integration/07-playwright-discovery-backend.md`).
    """

    engine: Literal["http", "playwright"] = "http"
    max_depth: int = Field(default=3, ge=0, le=10)
    max_pages: int = Field(default=50, ge=1, le=2000)
    rate_limit_rps: float = Field(default=5.0, gt=0.0, le=100.0)
    respect_robots: bool = True
    same_host_only: bool = True
    extra_allowed_hosts: tuple[str, ...] = Field(default_factory=tuple)
    request_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    openapi: DiscoveryOpenAPIConfig = Field(default_factory=lambda: DiscoveryOpenAPIConfig())
    graphql: DiscoveryGraphQLConfig = Field(default_factory=lambda: DiscoveryGraphQLConfig())


class PolicyConfig(SentinelModel):
    """`policy:` block."""

    min_quality_score: int = Field(default=85, ge=0, le=100)
    block_on_critical: bool = True
    block_on_high_security: bool = True
    max_flake_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    allow_medium_a11y: bool = False
    max_failed_p1_flows: int = Field(default=0, ge=0)


class ReportConfig(SentinelModel):
    """`report:` block."""

    output_dir: Path = Path(".sentinel/reports")
    formats: tuple[Literal["html", "json", "junit", "sarif", "markdown"], ...] = (
        "html",
        "json",
        "junit",
        "sarif",
    )


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class RootConfig(SentinelModel):
    """The fully-parsed `sentinel.config.yaml` (PRD §17.1)."""

    SCHEMA_VERSION: ClassVar[str] = CONFIG_SCHEMA_VERSION

    version: int = Field(default=1, ge=1)
    project: ProjectConfig
    source: SourceConfig = Field(default_factory=lambda: SourceConfig())
    target: TargetConfig
    auth: AuthConfig = Field(default_factory=lambda: AuthConfig())
    modules: ModulesConfig = Field(default_factory=lambda: ModulesConfig())
    security: SecurityConfig = Field(default_factory=lambda: SecurityConfig())
    performance: PerformanceConfig = Field(default_factory=lambda: PerformanceConfig())
    visual: VisualConfig = Field(default_factory=lambda: VisualConfig())
    discovery: DiscoveryConfig = Field(default_factory=lambda: DiscoveryConfig())
    policy: PolicyConfig = Field(default_factory=lambda: PolicyConfig())
    report: ReportConfig = Field(default_factory=lambda: ReportConfig())
    schema_version: str = Field(default=CONFIG_SCHEMA_VERSION)

    @model_validator(mode="after")
    def _destructive_requires_proof(self) -> RootConfig:
        if (
            self.security.mode == "authorized_destructive"
            and self.target.proof_of_authorization is None
        ):
            raise ValueError(
                "security.mode='authorized_destructive' requires "
                "target.proof_of_authorization to point at a signed doc."
            )
        return self


__all__ = [
    "RootConfig",
    "ProjectConfig",
    "SourceConfig",
    "TargetConfig",
    "AuthConfig",
    "ModulesConfig",
    "SecurityConfig",
    "PerformanceConfig",
    "PerformanceBudgets",
    "VisualConfig",
    "DiscoveryConfig",
    "DiscoveryOpenAPIConfig",
    "DiscoveryGraphQLConfig",
    "PolicyConfig",
    "ReportConfig",
]
