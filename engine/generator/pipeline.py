"""Generator pipeline (tasks 07.01-07.05 wired together).

Takes a :class:`TestPlan` + :class:`DiscoveryGraph` and produces the
full set of files the generator owns. Output is deterministic for a
given input — the same plan always yields byte-equal files (modulo
file paths derived from auto-generated IDs).

Call shape:

>>> pipeline = GeneratorPipeline()
>>> result = pipeline.generate(GenerationInputs(...))
>>> # result.files contains (Path, content) pairs; the CLI writes them.

The pipeline itself never touches the filesystem. The CLI command
(:mod:`sentinel_cli.commands.generate_cmd`) is responsible for writing
files (via :func:`engine.generator.writer.write_generated_files`) and
running the brittleness audit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from engine.domain.discovery_graph import DiscoveryGraph
from engine.domain.flow import Flow
from engine.domain.test_plan import TestPlan
from engine.generator.fixtures import (
    FixtureGenerationOptions,
    GeneratedFixture,
    generate_fixtures,
)
from engine.generator.page_objects import (
    GeneratedPageObject,
    PageObjectOptions,
    generate_page_objects,
)
from engine.generator.plan_md import (
    PLAN_FILE_NAME,
    GeneratedPlanInputs,
    read_prior_spec_paths,
    render_generated_plan_md,
)
from engine.generator.render import RenderError, render_template

SPEC_DIR_NAME: str = "sentinel"

FileKind = Literal["spec", "page-object", "fixture", "plan-md"]


@dataclass(frozen=True)
class GenerationOptions:
    """Tunable knobs for the pipeline."""

    page_object_options: PageObjectOptions = field(default_factory=PageObjectOptions)
    base_url: str = ""
    login_url: str | None = None
    username_env: str | None = None
    password_env: str | None = None
    user_create_endpoint: str | None = None
    user_delete_endpoint_template: str | None = None
    security_mode: str = "safe"
    default_perf_load_ms: int = 3_000
    default_perf_bytes: int = 1_500_000


@dataclass(frozen=True)
class GenerationInputs:
    """Inputs to :meth:`GeneratorPipeline.generate`."""

    plan: TestPlan
    graph: DiscoveryGraph
    out_dir: Path
    options: GenerationOptions = field(default_factory=GenerationOptions)
    prior_plan_md_path: Path | None = None


@dataclass(frozen=True)
class GeneratedFile:
    """One file the pipeline produced (path + body + provenance)."""

    path: Path
    content: str
    kind: FileKind
    flow_id: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    """Pipeline output. Contains files + per-section metadata."""

    files: tuple[GeneratedFile, ...]
    page_objects: tuple[GeneratedPageObject, ...]
    fixtures: tuple[GeneratedFixture, ...]
    plan_md_path: Path
    spec_paths: tuple[Path, ...]

    def files_by_kind(self, kind: FileKind) -> tuple[GeneratedFile, ...]:
        return tuple(f for f in self.files if f.kind == kind)


class GeneratorPipeline:
    """Stateless orchestrator. Construct once, call :meth:`generate` per plan."""

    def generate(self, inputs: GenerationInputs) -> GenerationResult:
        spec_root = inputs.out_dir / SPEC_DIR_NAME
        spec_files: list[GeneratedFile] = []
        spec_paths: list[Path] = []
        used_paths: dict[str, int] = {}

        for flow in inputs.plan.flows:
            rendered = self._render_flow(flow, inputs=inputs)
            if rendered is None:
                continue
            # If two flows produce the same slug-based filename (e.g. two
            # form submits on routes that slugify to the same string), add
            # a deterministic suffix derived from the flow's *order*
            # within the plan — which is stable across re-runs because the
            # planner sorts flows before emitting them.
            rel_path = rendered.path
            key = rel_path.as_posix()
            if key in used_paths:
                used_paths[key] += 1
                stem = rel_path.stem.removesuffix(".spec")
                rel_path = rel_path.with_name(f"{stem}_{used_paths[key]}.spec.ts")
            else:
                used_paths[key] = 1
            abs_path = spec_root / rel_path
            spec_files.append(
                GeneratedFile(
                    path=abs_path,
                    content=rendered.content,
                    kind="spec",
                    flow_id=flow.id,
                )
            )
            spec_paths.append(rel_path)

        page_objects = tuple(
            generate_page_objects(
                routes=inputs.graph.routes,
                elements=inputs.graph.elements,
                flows=inputs.plan.flows,
                out_dir=spec_root,
                options=inputs.options.page_object_options,
            )
        )
        po_files = tuple(
            GeneratedFile(
                path=spec_root / po.rel_path,
                content=po.source,
                kind="page-object",
            )
            for po in page_objects
        )

        fixture_options = FixtureGenerationOptions(
            base_url=inputs.options.base_url or inputs.plan.target_url,
            login_url=inputs.options.login_url,
            username_env=inputs.options.username_env,
            password_env=inputs.options.password_env,
            user_create_endpoint=inputs.options.user_create_endpoint,
            user_delete_endpoint_template=inputs.options.user_delete_endpoint_template,
            security_mode=inputs.options.security_mode,
        )
        fixtures = tuple(
            generate_fixtures(fixture_options, api_endpoints=inputs.graph.api_endpoints)
        )
        fixture_files = tuple(
            GeneratedFile(path=spec_root / f.rel_path, content=f.source, kind="fixture")
            for f in fixtures
        )

        prior_specs = (
            read_prior_spec_paths(inputs.prior_plan_md_path)
            if inputs.prior_plan_md_path is not None
            else []
        )
        plan_md_path = spec_root / PLAN_FILE_NAME
        plan_md_body = render_generated_plan_md(
            GeneratedPlanInputs(
                plan_id=inputs.plan.id,
                run_id=inputs.plan.run_id,
                target_url=inputs.plan.target_url,
                flows=inputs.plan.flows,
                spec_paths=spec_paths,
                page_object_paths=tuple(po.rel_path for po in page_objects),
                fixture_paths=tuple(f.rel_path for f in fixtures),
                audit_warnings=0,
                prior_spec_paths=tuple(prior_specs),
            )
        )
        plan_md_file = GeneratedFile(path=plan_md_path, content=plan_md_body, kind="plan-md")

        files = tuple(spec_files) + po_files + fixture_files + (plan_md_file,)
        return GenerationResult(
            files=files,
            page_objects=page_objects,
            fixtures=fixtures,
            plan_md_path=plan_md_path,
            spec_paths=tuple(spec_paths),
        )

    # ------------------------------------------------------------------
    # Per-flow rendering
    # ------------------------------------------------------------------

    @dataclass(frozen=True)
    class _RenderedSpec:
        path: Path
        content: str

    def _render_flow(
        self,
        flow: Flow,
        *,
        inputs: GenerationInputs,
    ) -> _RenderedSpec | None:
        extractor = flow.extractor or ""
        tags = _canonical_tag_set(flow)
        rel_path = Path(_spec_file_name(flow))

        if extractor in {"route.smoke", "route.auth_boundary"}:
            return self._render_smoke(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor.startswith("form.submit"):
            return self._render_form_submit(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor == "login":
            return self._render_login(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor == "signup":
            return self._render_signup(flow, tags=tags, rel_path=rel_path)
        if extractor == "logout":
            return self._render_logout(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor == "password_reset":
            return self._render_logout(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor == "crud":
            return self._render_crud_create(flow, tags=tags, rel_path=rel_path)
        if extractor in {"admin", "role"}:
            return self._render_role_boundary(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor == "payment_sandbox":
            return self._render_payment(flow, tags=tags, rel_path=rel_path)
        if extractor == "file_upload_download":
            return self._render_file_upload(flow, tags=tags, rel_path=rel_path)
        if extractor == "api.contract":
            return self._render_api_contract(flow, tags=tags, rel_path=rel_path)
        if extractor in {"a11y", "axe"}:
            return self._render_a11y(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        if extractor in {"perf", "performance"}:
            return self._render_perf(flow, tags=tags, rel_path=rel_path, inputs=inputs)
        # Default: emit a smoke spec for the first route the flow touches.
        return self._render_smoke(flow, tags=tags, rel_path=rel_path, inputs=inputs)

    # ------------------------------------------------------------------
    # Concrete renderers
    # ------------------------------------------------------------------

    def _render_smoke(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec | None:
        route_path = _first_route_path(flow, inputs.graph) or "/"
        content = render_template(
            "smoke.spec.ts.j2",
            {
                "describe_title": flow.name,
                "test_title": f"smoke {route_path}",
                "tags": list(tags),
                "route_path": route_path,
                "anchor_role": "main",
                "anchor_name": "",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_form_submit(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec | None:
        # Form submissions also get a smoke-shaped spec; richer codegen
        # for non-login forms lands when Phase 10 (Functional) extends
        # this pipeline.
        return self._render_smoke(flow, tags=tags, rel_path=rel_path, inputs=inputs)

    def _render_login(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec:
        login_path = _first_route_path(flow, inputs.graph) or "/login"
        content = render_template(
            "login.spec.ts.j2",
            {
                "tags": list(tags),
                "login_path": login_path,
                "email_env_name": inputs.options.username_env or "SENTINEL_USERNAME",
                "password_env_name": inputs.options.password_env or "SENTINEL_PASSWORD",
                "email_label": "email",
                "password_label": "password",
                "submit_label": "sign in|log in",
                "success_url_regex": "dashboard|home|app",
                "validation_message_regex": "required|invalid",
                "post_login_role": "navigation",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_signup(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
    ) -> _RenderedSpec:
        content = render_template(
            "signup.spec.ts.j2",
            {
                "tags": list(tags),
                "signup_path": "/signup",
                "sample_email": "sentinel+signup@example.com",
                "sample_password": "S3ntinel-Sample!",
                "email_label": "email",
                "password_label": "password",
                "confirm_password_label": "confirm password",
                "submit_label": "create account|sign up|register",
                "success_url_regex": "welcome|onboarding|dashboard",
                "invalid_email_regex": "valid email|invalid",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_logout(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec:
        start_path = _first_route_path(flow, inputs.graph) or "/dashboard"
        content = render_template(
            "logout.spec.ts.j2",
            {
                "tags": list(tags),
                "start_path": start_path,
                "logout_label": "log out|sign out|logout",
                "post_logout_url_regex": "login|sign[- ]?in|home|/",
                "post_logout_text": "logged out|signed out",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_crud_create(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
    ) -> _RenderedSpec:
        content = render_template(
            "crud_create.spec.ts.j2",
            {
                "tags": list(tags),
                "resource_title": flow.name,
                "resource_singular": "record",
                "create_path": "/records/new",
                "fields": [
                    {"label": "name", "sample_value": "Sentinel sample"},
                ],
                "submit_label": "create|save|submit",
                "success_url_regex": "records|created",
                "success_text": "created|saved",
                "required_error_regex": "required|cannot be empty",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_role_boundary(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec:
        path = _first_route_path(flow, inputs.graph) or "/admin"
        content = render_template(
            "role_boundary.spec.ts.j2",
            {
                "tags": list(tags),
                "describe_title": flow.name,
                "protected_path": path,
                "required_role": flow.required_auth_role or "admin",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_payment(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
    ) -> _RenderedSpec:
        content = render_template(
            "payment_sandbox.spec.ts.j2",
            {
                "tags": list(tags),
                "checkout_path": "/checkout",
                "sandbox_card_number": "4242 4242 4242 4242",
                "sandbox_card_exp": "12 / 34",
                "sandbox_card_cvc": "123",
                "card_number_label": "card number",
                "card_exp_label": "expiration|expiry",
                "card_cvc_label": "cvc|security code",
                "pay_label": "pay|complete order|checkout",
                "success_text": "thank you|payment confirmed",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_file_upload(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
    ) -> _RenderedSpec:
        content = render_template(
            "file_upload.spec.ts.j2",
            {
                "tags": list(tags),
                "upload_path": "/upload",
                "fixture_kind": "text",
                "fixture_file_name": "sentinel-fixture.txt",
                "fixture_mime_type": "text/plain",
                # Base64 for "SentinelQA test fixture\n"
                "fixture_base64": "U2VudGluZWxRQSB0ZXN0IGZpeHR1cmUK",
                "upload_label": "upload|attach|file",
                "submit_label": "upload|submit",
                "success_text": "uploaded|attached",
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_api_contract(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
    ) -> _RenderedSpec:
        method = "GET"
        path = "/"
        title = flow.name
        # Flow name layout from the deterministic planner:
        #   "api contract: <METHOD> <PATH>"
        match = re.match(r"api contract:\s*(\S+)\s+(.+)", flow.name)
        if match is not None:
            method = match.group(1).upper()
            path = match.group(2).strip()
        content = render_template(
            "api_contract.spec.ts.j2",
            {
                "tags": list(tags),
                "endpoint_title": title,
                "method": method,
                "path": path,
                "request_path": path,
                "request_body_json": "",
                "expected_status": [200, 201, 204] if method == "POST" else [200],
                "expected_content_type": "json",
                "skip_unauth_test": flow.required_auth_role is None,
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_a11y(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec:
        route_path = _first_route_path(flow, inputs.graph) or "/"
        content = render_template(
            "a11y_axe.spec.ts.j2",
            {
                "tags": list(tags),
                "route_title": flow.name,
                "route_path": route_path,
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)

    def _render_perf(
        self,
        flow: Flow,
        *,
        tags: Sequence[str],
        rel_path: Path,
        inputs: GenerationInputs,
    ) -> _RenderedSpec:
        route_path = _first_route_path(flow, inputs.graph) or "/"
        content = render_template(
            "perf_budget.spec.ts.j2",
            {
                "tags": list(tags),
                "route_title": flow.name,
                "route_path": route_path,
                "load_budget_ms": inputs.options.default_perf_load_ms,
                "bytes_budget": inputs.options.default_perf_bytes,
            },
        )
        return self._RenderedSpec(path=rel_path, content=content)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")
_ID_TAG_RE = re.compile(r"^(form|endpoint|element|route|element-?id):")
_FORM_ID_TAG_RE = re.compile(r"^form:(FRM-[A-Za-z0-9_-]+)$")
_ENDPOINT_ID_TAG_RE = re.compile(r"^endpoint:(API-[A-Za-z0-9_-]+)$")

# Extractor name → SentinelQA module (Phase 10.03). The mapping mirrors
# ``engine.planner.core._EXTRACTOR_TO_TEST_TYPE`` but for the canonical
# `@module:<name>` tag that the runner / CI modes filter on.
_EXTRACTOR_TO_MODULE: dict[str, str] = {
    "route.smoke": "functional",
    "route.auth_boundary": "functional",
    "form.submit": "functional",
    "login": "functional",
    "signup": "functional",
    "logout": "functional",
    "password_reset": "functional",
    "crud": "functional",
    "search_filter_sort": "functional",
    "admin": "functional",
    "role": "functional",
    "file_upload_download": "functional",
    "payment_sandbox": "functional",
    "notification": "functional",
    "api.contract": "api",
    "a11y": "a11y",
    "axe": "a11y",
    "perf": "performance",
    "performance": "performance",
}


def _canonical_tag_set(flow: Flow) -> list[str]:
    """Return the canonical Playwright tag set for ``flow`` (Phase 10.03).

    The set always contains, in order:

    1. ``@p0``..``@p3`` derived from ``flow.priority``.
    2. ``@module:<name>`` derived from the extractor → module mapping.
    3. ``@flow:<extractor>`` — the planner extractor that produced the flow.
    4. ``@risk:<level>`` — the canonical risk bucket.
    5. Any planner-provided tags that survive :func:`_stable_tags` (these
       are non-ID, content-stable annotations like ``auth_boundary`` or
       ``llm_audit_candidate``).
    """

    extractor = flow.extractor or "unknown"
    module_name = _EXTRACTOR_TO_MODULE.get(extractor, "functional")
    base: list[str] = [
        f"@{flow.priority.lower()}",
        f"@module:{module_name}",
        f"@flow:{extractor}",
        f"@risk:{flow.risk}",
    ]
    for tag in _stable_tags(flow.tags):
        prefixed = f"@{tag}"
        if prefixed not in base:
            base.append(prefixed)
    return base


def _stable_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Strip ID-bearing tags so generated specs are byte-stable across runs.

    The planner emits ``form:FRM-...``, ``endpoint:API-...``, etc. for
    the audit trail. ``FRM-*`` and ``API-*`` IDs come from the
    discovery graph (loaded once from JSON) so they ARE stable across
    re-runs; we keep those for plan provenance. ``FLW-*`` / ``RUN-*``
    style IDs are auto-generated per planner run and would break
    spec idempotency, so they are dropped.
    """

    out: list[str] = []
    for t in tags:
        m = _ID_TAG_RE.match(t)
        if m is None:
            out.append(t)
            continue
        # Keep the form:/endpoint: tags that reference discovery IDs.
        if _FORM_ID_TAG_RE.match(t) or _ENDPOINT_ID_TAG_RE.match(t):
            out.append(t)
    return tuple(out)


def _stable_disambiguator(flow: Flow) -> str | None:
    """Return a content-stable suffix for ``flow``, or None if not needed.

    The suffix is derived from discovery-graph IDs (form, endpoint)
    surfaced in ``flow.tags``. Those IDs come from the persisted
    discovery.json so they are byte-stable across re-runs and provide
    a deterministic way to disambiguate flows whose ``(extractor, name)``
    pair would otherwise produce the same spec filename.
    """

    for tag in flow.tags:
        m = _FORM_ID_TAG_RE.match(tag) or _ENDPOINT_ID_TAG_RE.match(tag)
        if m is not None:
            return m.group(1).lower().replace("-", "_")
    return None


def _spec_file_name(flow: Flow) -> str:
    """Return the relative spec file name (under tests/sentinel/) for ``flow``.

    Name is derived from the flow's extractor + name slug + a stable
    disambiguator from discovery IDs (when available) — never from the
    auto-generated ``flow.id`` — so re-running ``sentinel generate``
    against the same plan produces byte-identical filenames.
    """

    extractor = flow.extractor or "spec"
    raw = f"{extractor}_{flow.name}"
    slug = _SAFE_NAME.sub("_", raw).strip("_").lower()
    if not slug:
        slug = "flow"
    disambig = _stable_disambiguator(flow)
    if disambig is not None:
        slug = f"{slug}_{disambig}"
    # Truncate so OS path length limits stay safe (255 chars typical).
    slug = slug[:120]
    return f"{slug}.spec.ts"


def _first_route_path(flow: Flow, graph: DiscoveryGraph) -> str | None:
    route_ids = [s.target_route_id for s in flow.steps if s.target_route_id is not None]
    if not route_ids:
        return None
    first = route_ids[0]
    for route in graph.routes:
        if route.id == first:
            return route.path
    return None


__all__ = [
    "FileKind",
    "GeneratedFile",
    "GenerationInputs",
    "GenerationOptions",
    "GenerationResult",
    "GeneratorPipeline",
    "RenderError",
    "SPEC_DIR_NAME",
]
