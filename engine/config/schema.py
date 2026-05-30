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


class AuthSecondUserConfig(SentinelModel):
    """`auth.second_user:` block (Phase 13.07, IDOR check).

    Names env vars holding the credentials for a *second* test user, used
    by the IDOR smoke check to compare resource access across accounts.
    Without this block, the IDOR check is skipped with an ``info`` note
    rather than fabricating a finding.
    """

    username_env: str | None = Field(default=None, max_length=128)
    password_env: str | None = Field(default=None, max_length=128)
    token_env: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)


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
    second_user: AuthSecondUserConfig = Field(
        default_factory=lambda: AuthSecondUserConfig(),
    )


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


class SecurityChecksConfig(SentinelModel):
    """`security.checks:` block (Phase 13, ADR-0018).

    Boolean per-check toggles. Defaults follow CLAUDE §26 "safe by default":

    - Always-on safe HTTP checks: headers, cookies, CORS, CSRF, reflected
      XSS, IDOR, frontend secrets.
    - Off by default (require explicit opt-in + mode/proof escalation):
      stored XSS (``authorized_destructive`` + proof), SQLi (local mode
      or ``authorized_destructive`` + proof), SAST (semgrep is opt-in
      because it has heavy runtime cost).
    """

    headers: bool = True
    cookies: bool = True
    cors: bool = True
    csrf: bool = True
    xss_reflected: bool = True
    xss_stored: bool = False
    sqli: bool = False
    idor: bool = True
    frontend_secrets: bool = True
    dependency_scan: bool = True
    sast: bool = False


class DependencyScannersConfig(SentinelModel):
    """`security.dependency_scanners:` block (Phase 13.09).

    Per-tool toggles. ``pip-audit`` and ``npm audit`` default ON because
    every modern project ships at least one of the matching lockfiles;
    each adapter no-ops gracefully when the lockfile is missing. The
    multi-language ``osv-scanner`` is opt-in (its scan can be slow).
    ``semgrep`` is the optional SAST adapter (separate from
    ``security.checks.sast`` because users may enable the broad SAST
    capability while picking a non-semgrep engine in the future).
    """

    pip_audit: bool = True
    npm_audit: bool = True
    osv_scanner: bool = False
    semgrep: bool = False


class SecurityConfig(SentinelModel):
    """`security:` block (Phase 13, ADR-0018).

    The Phase-13 SecurityModule reads ``checks`` to decide which probes
    to run, ``dependency_scanners`` to drive the dep-scan adapters, and
    ``routes`` to enumerate the endpoint set (mirrors the
    ``performance.routes`` / ``accessibility.routes`` pattern). The
    ``mode`` knob escalates the safety boundary: dangerous probes (stored
    XSS, SQLi) only run with ``authorized_destructive`` mode AND a valid
    proof-of-authorization document (see
    :class:`engine.policy.proof_of_authorization.ProofOfAuthorization`).
    """

    mode: Mode = "safe"
    destructive_tests: bool = False
    max_requests_per_second: int = Field(default=5, ge=1, le=1000)
    allowed_payload_level: Literal["none", "low", "medium", "high"] = "low"
    checks: SecurityChecksConfig = Field(default_factory=lambda: SecurityChecksConfig())
    dependency_scanners: DependencyScannersConfig = Field(
        default_factory=lambda: DependencyScannersConfig()
    )
    routes: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    request_timeout_seconds: float = Field(default=15.0, gt=0.0, le=300.0)

    @model_validator(mode="after")
    def _destructive_requires_mode(self) -> SecurityConfig:
        if self.destructive_tests and self.mode != "authorized_destructive":
            raise ValueError(
                "security.destructive_tests=true requires "
                "security.mode='authorized_destructive'."
            )
        return self

    @model_validator(mode="after")
    def _stored_xss_requires_destructive(self) -> SecurityConfig:
        if self.checks.xss_stored and self.mode != "authorized_destructive":
            raise ValueError(
                "security.checks.xss_stored=true requires "
                "security.mode='authorized_destructive' "
                "(stored XSS writes state; see PRD §10.7 + CLAUDE.md §26)."
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


class VisualViewportConfig(SentinelModel):
    """One entry in ``visual.viewports`` (Phase 21.05).

    The viewport ``name`` is also the directory segment under
    ``baselines_dir`` and the file segment in the run's ``visual/``
    artifact tree (``current/<viewport>/<route-slug>.png``).
    """

    name: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    width: int = Field(gt=0, le=10000)
    height: int = Field(gt=0, le=10000)


class VisualMaskConfig(SentinelModel):
    """One entry in ``visual.masks`` (Phase 21.04).

    ``route`` matches the captured route slug (the same value used by
    the baseline filename); ``selector`` is the CSS selector the TS
    capture helper hides before screenshot. The Python diff layer ALSO
    accepts a static rectangle (``rect``) so test fixtures can verify
    masking without driving Playwright (PRD §10.6 + CLAUDE §29).
    """

    route: str = Field(min_length=1, max_length=512)
    selector: str | None = Field(default=None, max_length=2048)
    rect: tuple[int, int, int, int] | None = None
    reason: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def _selector_or_rect(self) -> VisualMaskConfig:
        if self.selector is None and self.rect is None:
            raise ValueError(
                "visual.masks entry must define either 'selector' (captured at "
                "screenshot time) or 'rect' (applied by the diff layer)."
            )
        return self


class VisualPerceptualConfig(SentinelModel):
    """`visual.perceptual:` block (Phase 21.03).

    SSIM-based perceptual diff. When enabled, a finding only fires when
    BOTH the pixel threshold AND the SSIM threshold are exceeded — the
    perceptual layer is a noise filter, not a second alarm.
    """

    enabled: bool = False
    min_similarity: float = Field(default=0.98, ge=0.0, le=1.0)


_DEFAULT_VIEWPORTS: tuple[VisualViewportConfig, ...] = (
    VisualViewportConfig(name="mobile", width=375, height=812),
    VisualViewportConfig(name="tablet", width=768, height=1024),
    VisualViewportConfig(name="desktop", width=1280, height=800),
)


class VisualConfig(SentinelModel):
    """`visual:` block (PRD §10.6, CLAUDE §29).

    The visual module consumes already-captured PNGs from a run's
    ``visual/current/`` tree and diffs them against the baselines under
    ``baselines_dir``. Baselines never auto-accept in CI: the CLI
    refuses ``--accept`` when ``--ci`` (or the ``CI`` / ``SENTINEL_CI``
    env var) is set.
    """

    baselines_dir: Path = Path(".sentinel/baselines")
    threshold: float = Field(default=0.02, ge=0.0, le=1.0)
    mask_dynamic_content: bool = True
    viewports: tuple[VisualViewportConfig, ...] = Field(
        default_factory=lambda: _DEFAULT_VIEWPORTS,
        max_length=16,
    )
    masks: tuple[VisualMaskConfig, ...] = Field(default_factory=tuple, max_length=256)
    perceptual: VisualPerceptualConfig = Field(default_factory=lambda: VisualPerceptualConfig())

    @field_validator("viewports")
    @classmethod
    def _unique_viewport_names(
        cls, value: tuple[VisualViewportConfig, ...]
    ) -> tuple[VisualViewportConfig, ...]:
        seen: set[str] = set()
        for vp in value:
            if vp.name in seen:
                raise ValueError(f"Duplicate visual.viewports.name: {vp.name!r}.")
            seen.add(vp.name)
        return value


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

    Two backends ship:

    - ``engine: "http"`` (default) — the Phase 05 HTTP-first crawler.
      Lightweight; works for SSR apps; produces an empty graph for
      client-rendered SPAs.
    - ``engine: "playwright"`` (Phase 17 task 07) — drives Chromium via
      ``sentinel-ts discover`` and consumes ``discovery.page`` /
      ``discovery.endpoint`` JSONL events. Requires the Phase 04 TS
      runtime to be installed (``pnpm install`` + browser provisioning).
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


class ApiAuthTestUser(SentinelModel):
    """One entry in ``api.auth_test_users`` (Phase 22.05).

    Names env vars holding bearer tokens for the auth-matrix check.
    Secrets are NEVER inlined — only ``token_env`` is accepted, matching
    :class:`AuthConfig` and CLAUDE.md §33. ``label`` identifies the user
    in findings (``user_a``, ``admin``, etc.). ``role`` is informational
    and tags findings so the report distinguishes "low-priv user got
    200 on /admin" from "anonymous got 200 on /admin".
    """

    label: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    token_env: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=64)


class ApiConfig(SentinelModel):
    """`api:` block (Phase 22, PRD §10.3, CLAUDE.md §30).

    Drives the ApiModule. Contract / negative / auth / latency /
    pagination / error-shape / backward-compat checks are individually
    gated through ``enabled_checks`` so operators can subset what runs
    (PRD §10.3). Payload bounds are clamped so a misconfigured run
    cannot turn into accidental fuzzing — ``negative_max_payload_kb``
    is capped at 64 KB, ``negative_max_variants_per_endpoint`` at 16.
    Aggressive fuzzing has **no** opt-in flag here, anywhere in the
    schema, or in any CLI surface (CLAUDE.md §30 + the
    ``tests/security/test_api_no_aggressive_flags.py`` guard).
    """

    enabled_checks: tuple[
        Literal[
            "contract",
            "negative",
            "auth",
            "latency",
            "pagination",
            "error_shape",
            "backward_compat",
        ],
        ...,
    ] = (
        "contract",
        "negative",
        "auth",
        "latency",
        "pagination",
        "error_shape",
        "backward_compat",
    )
    openapi_path: Path | None = None
    graphql_path: Path | None = None
    graphql_endpoint: str = Field(default="/graphql", max_length=2048)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    rate_per_second: float = Field(default=5.0, gt=0.0, le=100.0)
    negative_max_payload_kb: int = Field(default=16, ge=1, le=64)
    negative_max_variants_per_endpoint: int = Field(default=4, ge=1, le=16)
    auth_test_users: tuple[ApiAuthTestUser, ...] = Field(default_factory=tuple, max_length=8)
    pagination_max_pages: int = Field(default=10, ge=1, le=100)
    latency_min_samples: int = Field(default=5, ge=1, le=200)
    sample_endpoints_max: int = Field(default=50, ge=1, le=500)
    routes: tuple[str, ...] = Field(default_factory=tuple, max_length=200)

    @field_validator("enabled_checks")
    @classmethod
    def _enabled_checks_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for item in value:
            if item in seen:
                raise ValueError(f"api.enabled_checks duplicate entry: {item!r}.")
            seen.add(item)
        return value

    @field_validator("auth_test_users")
    @classmethod
    def _auth_users_unique_labels(
        cls, value: tuple[ApiAuthTestUser, ...]
    ) -> tuple[ApiAuthTestUser, ...]:
        seen: set[str] = set()
        for entry in value:
            if entry.label in seen:
                raise ValueError(f"api.auth_test_users duplicate label: {entry.label!r}.")
            seen.add(entry.label)
        return value


class ChaosConfig(SentinelModel):
    """`chaos:` block (Phase 23, PRD §10.8, CLAUDE.md §6, ADR-0028).

    Drives the ChaosModule. The module is OFF by default in
    :class:`ModulesConfig` (``modules.chaos = false``); this block only
    configures which categories / scenarios the module exercises *when*
    it is opted in (via ``modules.chaos = true``, ``sentinel chaos
    ...``, or the CI ``nightly`` preset). Defaults mirror PRD §10.8:
    all four categories enabled with no scenario subsetting.

    Safety boundary (CLAUDE.md §6): no field here lets an operator
    turn the module into an evasion tool. There is no ``aggressive``
    knob, no proxy-rotation knob, no detection-bypass knob — and the
    ``tests/security/test_chaos_no_evasion_flags.py`` guard greps the
    package + CLI to keep it that way.
    """

    enabled_categories: tuple[Literal["network", "session", "ux", "data"], ...] = (
        "network",
        "session",
        "ux",
        "data",
    )
    enabled_scenarios: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    flows: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    events_path: Path | None = None
    slow_3g_kbps: int = Field(default=400, ge=100, le=10_000)
    slow_3g_rtt_ms: int = Field(default=400, ge=50, le=5_000)
    api_timeout_abort_ms: int = Field(default=30_000, ge=1_000, le=120_000)
    large_dataset_items: int = Field(default=1000, ge=100, le=10_000)

    @field_validator("enabled_categories")
    @classmethod
    def _categories_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for item in value:
            if item in seen:
                raise ValueError(f"chaos.enabled_categories duplicate entry: {item!r}.")
            seen.add(item)
        return value

    @field_validator("enabled_scenarios")
    @classmethod
    def _scenarios_shape(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for item in value:
            if not item or len(item) > 128:
                raise ValueError("chaos.enabled_scenarios entries must be 1..128 chars.")
            if item in seen:
                raise ValueError(f"chaos.enabled_scenarios duplicate entry: {item!r}.")
            seen.add(item)
        return value


class PolicyGitHubIntegrationConfig(SentinelModel):
    """`policy.github:` block (Phase 25.04).

    Controls the Phase 25 deeper GitHub integration. Off by default —
    flipping ``auto_create_issue`` to ``true`` lets the caller open
    GitHub issues for critical findings via
    :func:`integrations.github.issue.create_issue_for_finding`. The
    poster also checks this flag at call time, so a misconfigured CI
    cannot bypass the gate by setting it directly in Python.
    """

    auto_create_issue: bool = False


class PolicyJiraIntegrationConfig(SentinelModel):
    """`policy.integrations.jira:` block (Phase 25.06)."""

    project_key: str | None = Field(default=None, max_length=64)
    base_url: str | None = Field(default=None, max_length=256)


class PolicyLinearIntegrationConfig(SentinelModel):
    """`policy.integrations.linear:` block (Phase 25.06)."""

    team_id: str | None = Field(default=None, max_length=64)


class PolicySlackIntegrationConfig(SentinelModel):
    """`policy.integrations.slack:` block (Phase 25.03)."""

    enabled: bool = False
    webhook_env: str = Field(default="SLACK_WEBHOOK_URL", max_length=128)


class PolicyIntegrationsConfig(SentinelModel):
    """`policy.integrations:` umbrella for Phase 25 adapters."""

    jira: PolicyJiraIntegrationConfig = Field(default_factory=lambda: PolicyJiraIntegrationConfig())
    linear: PolicyLinearIntegrationConfig = Field(
        default_factory=lambda: PolicyLinearIntegrationConfig()
    )
    slack: PolicySlackIntegrationConfig = Field(
        default_factory=lambda: PolicySlackIntegrationConfig()
    )


class PolicyConfig(SentinelModel):
    """`policy:` block (PRD §17.1, §19.4).

    The severity-penalty fields default to the midpoint of the
    PRD §19.2 / CLAUDE.md §25 ranges (high 10..25 -> 17.5; medium 3..10
    -> 6.5; low 1..3 -> 2.0). Critical findings always carry a fixed
    penalty of 30 so the numeric score still reflects severity even
    when the run is otherwise blocked by `block_on_critical`.
    """

    min_quality_score: int = Field(default=85, ge=0, le=100)
    block_on_critical: bool = True
    block_on_high_security: bool = True
    max_flake_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    allow_medium_a11y: bool = False
    max_failed_p1_flows: int = Field(default=0, ge=0)
    severity_penalty_high: float = Field(default=17.5, ge=10.0, le=25.0)
    severity_penalty_medium: float = Field(default=6.5, ge=3.0, le=10.0)
    severity_penalty_low: float = Field(default=2.0, ge=1.0, le=3.0)
    github: PolicyGitHubIntegrationConfig = Field(
        default_factory=lambda: PolicyGitHubIntegrationConfig()
    )
    integrations: PolicyIntegrationsConfig = Field(
        default_factory=lambda: PolicyIntegrationsConfig()
    )


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


class HealerConfig(SentinelModel):
    """`healer:` block (Phase 20, ADR-0025, CLAUDE.md §23).

    Drives the self-repair pipeline. ``auto_apply`` is the operator's
    posture toward applying healer proposals without review:

    - ``off``: never auto-apply; every proposal goes to the human
      review queue (default).
    - ``safe``: auto-apply ``locator`` and ``wait`` repairs at or above
      ``auto_apply_threshold``. Never assertion-stabilization repairs.
    - ``aggressive``: also auto-apply ``fixture`` repairs and
      ``assertion`` repairs (the latter still require
      ``sentinel fix --allow-weaken``).

    ``auto_apply_threshold`` is the minimum confidence a proposal must
    carry to be eligible for auto-apply. Anything below the threshold
    is review-only regardless of mode.
    """

    auto_apply: Literal["off", "safe", "aggressive"] = "off"
    auto_apply_threshold: float = Field(default=0.9, ge=0.5, le=1.0)


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
    api: ApiConfig = Field(default_factory=lambda: ApiConfig())
    chaos: ChaosConfig = Field(default_factory=lambda: ChaosConfig())
    policy: PolicyConfig = Field(default_factory=lambda: PolicyConfig())
    runner: RunnerConfig = Field(default_factory=lambda: RunnerConfig())
    healer: HealerConfig = Field(default_factory=lambda: HealerConfig())
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
    "AuthSecondUserConfig",
    "ModulesConfig",
    "SecurityConfig",
    "SecurityChecksConfig",
    "DependencyScannersConfig",
    "PerformanceConfig",
    "PerformanceBudgets",
    "VisualConfig",
    "VisualMaskConfig",
    "VisualPerceptualConfig",
    "VisualViewportConfig",
    "DiscoveryConfig",
    "DiscoveryOpenAPIConfig",
    "DiscoveryGraphQLConfig",
    "PlannerConfig",
    "PlannerLlmConfig",
    "AnalyzerConfig",
    "AnalyzerLlmConfig",
    "AccessibilityConfig",
    "AccessibilityAxeConfig",
    "ApiAuthTestUser",
    "ApiConfig",
    "ChaosConfig",
    "PolicyConfig",
    "PolicyGitHubIntegrationConfig",
    "PolicyIntegrationsConfig",
    "PolicyJiraIntegrationConfig",
    "PolicyLinearIntegrationConfig",
    "PolicySlackIntegrationConfig",
    "RunnerConfig",
    "RunnerRetriesConfig",
    "RunnerQuarantineConfig",
    "HealerConfig",
    "ReportConfig",
]
