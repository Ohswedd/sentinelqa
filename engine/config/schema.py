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
    """`performance.budgets:` block (PRD §10.5, CLAUDE §27)."""

    lcp_ms: int = Field(default=2500, ge=0)
    cls: float = Field(default=0.1, ge=0)
    inp_ms: int = Field(default=200, ge=0)
    ttfb_ms: int = Field(default=600, ge=0)
    api_p95_ms: int = Field(default=500, ge=0)
    js_total_kb: int = Field(default=500, ge=0)
    long_task_total_ms: int = Field(default=200, ge=0)
    dom_growth_pct: float = Field(default=10.0, ge=0.0, le=1000.0)
    memory_growth_pct: float = Field(default=20.0, ge=0.0, le=1000.0)


class PerformanceConfig(SentinelModel):
    """`performance:` block (Phase 12, ADR-0017).

    Performance checks are explicitly **synthetic** lab measurements (CLAUDE §27);
    the module never claims to mirror Real-User Monitoring. Routes default to
    empty so ``sentinel audit`` short-circuits the module unless the caller
    (CLI, SDK, or `discovery.json`) supplies a plan. ``samples`` is the per-route
    sample count for LCP/CLS/INP/TTFB; the module reports the median of those
    samples. ``repeated_nav_samples`` is the visit count used by the memory-leak
    heuristic.
    """

    budgets: PerformanceBudgets = Field(default_factory=PerformanceBudgets)
    routes: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    samples: int = Field(default=3, ge=1, le=20)
    repeated_nav_samples: int = Field(default=5, ge=2, le=50)
    api_min_samples_for_p95: int = Field(default=5, ge=1, le=200)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    api_path_allowlist: tuple[str, ...] = Field(default_factory=tuple, max_length=200)


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


class PlannerLlmConfig(SentinelModel):
    """`planner.llm:` block (Phase 06.04, ADR-0011).

    The deterministic planner ships in Phase 06; the LLM adapter is opt-in
    behind ``enabled``. Provider keys are never inlined — only env-var
    names go in YAML, in line with :class:`AuthConfig` and CLAUDE §33.
    """

    enabled: bool = False
    provider: Literal["null", "openai", "anthropic"] = "null"
    model: str = Field(default="", max_length=200)
    api_key_env: str | None = Field(default=None, max_length=128)
    max_proposals: int = Field(default=10, ge=0, le=200)
    max_usd_per_run: float = Field(default=0.50, ge=0.0, le=100.0)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)


class PlannerConfig(SentinelModel):
    """`planner:` block."""

    llm: PlannerLlmConfig = Field(default_factory=lambda: PlannerLlmConfig())


class AnalyzerLlmConfig(SentinelModel):
    """`analyzer.llm:` block (Phase 09.05, ADR-0014).

    The deterministic analyzer ships in Phase 09; the LLM explainer is
    opt-in behind ``enabled``. Provider keys are never inlined — only
    env-var names go in YAML, in line with :class:`AuthConfig` and
    CLAUDE §33. The explainer adds at most one sentence of refinement
    to each deterministic hypothesis; it never replaces the
    deterministic category, hypothesis, or confidence (CLAUDE §23).
    """

    enabled: bool = False
    provider: Literal["null", "openai", "anthropic"] = "null"
    model: str = Field(default="", max_length=200)
    api_key_env: str | None = Field(default=None, max_length=128)
    max_usd_per_run: float = Field(default=0.25, ge=0.0, le=100.0)
    request_timeout_seconds: float = Field(default=20.0, gt=0.0, le=300.0)


class AnalyzerConfig(SentinelModel):
    """`analyzer:` block (Phase 09, ADR-0014)."""

    llm: AnalyzerLlmConfig = Field(default_factory=lambda: AnalyzerLlmConfig())


class AccessibilityAxeConfig(SentinelModel):
    """`accessibility.axe:` block (Phase 11, ADR-0016)."""

    tags: tuple[str, ...] = Field(
        default=("wcag2a", "wcag2aa", "best-practice"),
        max_length=32,
    )

    @field_validator("tags")
    @classmethod
    def _tags_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("accessibility.axe.tags must list at least one axe tag.")
        for tag in value:
            if not tag or len(tag) > 64:
                raise ValueError(f"accessibility.axe.tag {tag!r} must be 1-64 chars.")
        return value


class AccessibilityConfig(SentinelModel):
    """`accessibility:` block (Phase 11, ADR-0016).

    Drives the AccessibilityModule. ``axe.tags`` defaults to the WCAG 2.0
    A + AA rule sets plus axe's curated best-practice set so the module
    catches common defects without overclaiming compliance (CLAUDE §28).
    """

    axe: AccessibilityAxeConfig = Field(
        default_factory=lambda: AccessibilityAxeConfig(),
    )
    routes: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    keyboard_max_tabs: int = Field(default=200, ge=1, le=2000)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)


class PolicyConfig(SentinelModel):
    """`policy:` block."""

    min_quality_score: int = Field(default=85, ge=0, le=100)
    block_on_critical: bool = True
    block_on_high_security: bool = True
    max_flake_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    allow_medium_a11y: bool = False
    max_failed_p1_flows: int = Field(default=0, ge=0)


class RunnerRetriesConfig(SentinelModel):
    """`runner.retries:` block (Phase 08.04)."""

    max: int = Field(default=1, ge=0, le=10)
    backoff_ms: int = Field(default=1000, ge=0, le=60_000)


class RunnerQuarantineConfig(SentinelModel):
    """`runner.quarantine:` block (Phase 08.04, CLAUDE.md §23).

    Quarantined tests run but their result does NOT block the quality gate.
    The list is enforced strictly: each entry must include an ``expires_at``
    date no more than ``max_age_days`` from today, plus an issue reference
    so the quarantine cannot rot silently.
    """

    path: Path = Path("tests/sentinel/.quarantine.yaml")
    max_age_days: int = Field(default=14, ge=1, le=90)


class RunnerConfig(SentinelModel):
    """`runner:` block (Phase 08, ADR-0013).

    Drives both the local Playwright runner and the Docker runner. The
    shape is stable across executors so users can flip ``runner.docker``
    on/off without other config edits.
    """

    workers: int | Literal["auto"] = Field(default="auto")
    shards: str | None = Field(default=None, max_length=16, pattern=r"^[1-9][0-9]*/[1-9][0-9]*$")
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    docker: bool = False
    docker_image: str = Field(default="mcr.microsoft.com/playwright:v1.49.0-jammy", max_length=256)
    retries: RunnerRetriesConfig = Field(default_factory=lambda: RunnerRetriesConfig())
    quarantine: RunnerQuarantineConfig = Field(default_factory=lambda: RunnerQuarantineConfig())

    @model_validator(mode="after")
    def _shard_index_within_total(self) -> RunnerConfig:
        if self.shards is None:
            return self
        current_s, total_s = self.shards.split("/", 1)
        current = int(current_s)
        total = int(total_s)
        if current > total:
            raise ValueError(
                f"runner.shards={self.shards!r}: shard index ({current}) "
                f"must be ≤ total ({total})."
            )
        return self


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
    planner: PlannerConfig = Field(default_factory=lambda: PlannerConfig())
    analyzer: AnalyzerConfig = Field(default_factory=lambda: AnalyzerConfig())
    accessibility: AccessibilityConfig = Field(default_factory=lambda: AccessibilityConfig())
    policy: PolicyConfig = Field(default_factory=lambda: PolicyConfig())
    runner: RunnerConfig = Field(default_factory=lambda: RunnerConfig())
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
    "PlannerConfig",
    "PlannerLlmConfig",
    "AnalyzerConfig",
    "AnalyzerLlmConfig",
    "AccessibilityConfig",
    "AccessibilityAxeConfig",
    "PolicyConfig",
    "RunnerConfig",
    "RunnerRetriesConfig",
    "RunnerQuarantineConfig",
    "ReportConfig",
]
