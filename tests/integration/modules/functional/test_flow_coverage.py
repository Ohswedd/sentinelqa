"""Flow-coverage integration test (Phase 10.02).

Builds a representative :class:`DiscoveryGraph` covering every our product spec1
flow type, runs it through the deterministic planner + generator, and
asserts that each named flow type produces at least one generated spec
whose canonical tag set names the right ``@flow:`` / ``@module:`` /
``@risk:`` values.

This is a wiring test — it does not exercise the Playwright runner.
The runner sweep is in ``tests/integration/modules/functional/test_runner_sweep.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.config.loader import load_config
from engine.domain.api_endpoint import ApiEndpoint
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator
from engine.domain.risk_map import RiskMap
from engine.domain.route import Route
from engine.generator import (
    GenerationInputs,
    GenerationOptions,
    GeneratorPipeline,
)
from engine.planner.core import DeterministicPlanner


@pytest.fixture
def representative_graph(tmp_path: Path) -> tuple[DiscoveryGraph, RiskMap, IdGenerator]:
    ids = IdGenerator()
    routes = (
        Route(id=ids.new("RT"), path="/login"),
        Route(id=ids.new("RT"), path="/signup"),
        Route(id=ids.new("RT"), path="/logout"),
        Route(id=ids.new("RT"), path="/forgot-password"),
        Route(id=ids.new("RT"), path="/records"),
        Route(id=ids.new("RT"), path="/records/[id]"),
        Route(id=ids.new("RT"), path="/search?q="),
        Route(id=ids.new("RT"), path="/admin", auth_required=True),
        Route(id=ids.new("RT"), path="/account/upload"),
        Route(id=ids.new("RT"), path="/checkout"),
        Route(id=ids.new("RT"), path="/verify/[token]"),
    )
    login_form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/login",
        method="POST",
        fields=(
            FormField(name="email", type="email", required=True),
            FormField(name="password", type="password", required=True),
        ),
    )
    upload_form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/account/upload",
        method="POST",
        fields=(FormField(name="attachment", type="file", required=True),),
    )
    forms = (login_form, upload_form)
    api_endpoints = (
        ApiEndpoint(
            id=ids.new("API"),
            method="GET",
            path="/api/records",
            source="openapi",
            auth_strategy="bearer",
        ),
    )
    boundaries = (
        AuthBoundary(
            route_id=routes[7].id,  # /admin
            required_role="admin",
        ),
    )
    graph = DiscoveryGraph(
        id=ids.new("DG"),
        routes=routes,
        forms=forms,
        api_endpoints=api_endpoints,
        auth_boundaries=boundaries,
    )
    # Risk map: keep flat (every route gets default risk).
    risk = RiskMap(id=ids.new("RM"), entries=())
    return graph, risk, ids


def _write_config(tmp_path: Path) -> Path:
    p = tmp_path / "sentinel.config.yaml"
    p.write_text(
        "version: 1\nproject:\n  name: demo\n"
        "target:\n  base_url: http://localhost:3000\n  allowed_hosts: [localhost]\n",
        encoding="utf-8",
    )
    return p


def test_every_prd_10_1_flow_type_emits_a_spec(
    tmp_path: Path,
    representative_graph: tuple[DiscoveryGraph, RiskMap, IdGenerator],
) -> None:
    graph, risk, ids = representative_graph
    config = load_config(_write_config(tmp_path))

    plan = (
        DeterministicPlanner(id_generator=ids)
        .plan(graph, risk, config, run_id="RUN-FLWCAAAAAAAA")
        .plan
    )

    extractors_seen = {flow.extractor for flow in plan.flows}
    # our product spec1 named flow types: login, signup, logout, password reset,
    # crud, search/filter/sort, admin, role, file upload, notification,
    # payment sandbox. Plus the deterministic ones the planner core
    # always emits: route.smoke, route.auth_boundary, form.submit,
    # api.contract.
    must_include = {
        "login",
        "signup",
        "logout",
        "password_reset",
        "crud",
        "search_filter_sort",
        "admin",
        "role",
        "file_upload_download",
        "payment_sandbox",
        "notification",
        "route.smoke",
        "route.auth_boundary",
        "form.submit",
        "api.contract",
    }
    missing = must_include - extractors_seen
    assert not missing, f"missing our product spec1 flow types: {sorted(missing)}"


def test_generator_emits_canonical_tags_for_every_flow(
    tmp_path: Path,
    representative_graph: tuple[DiscoveryGraph, RiskMap, IdGenerator],
) -> None:
    graph, risk, ids = representative_graph
    config = load_config(_write_config(tmp_path))
    plan = (
        DeterministicPlanner(id_generator=ids)
        .plan(graph, risk, config, run_id="RUN-TAGCAAAAAAAA")
        .plan
    )

    pipeline = GeneratorPipeline()
    out_dir = tmp_path / "tests"
    result = pipeline.generate(
        GenerationInputs(
            plan=plan,
            graph=graph,
            out_dir=out_dir,
            options=GenerationOptions(
                base_url="http://localhost:3000",
                security_mode="safe",
            ),
        )
    )

    spec_contents = [(f.path.name, f.content) for f in result.files_by_kind("spec")]
    assert spec_contents, "expected at least one spec"

    for name, content in spec_contents:
        # Every functional / api / a11y / perf spec must declare a
        # priority tag and a module tag.
        assert (
            "@p0" in content or "@p1" in content or "@p2" in content or "@p3" in content
        ), f"{name} missing priority tag"
        assert "@module:" in content, f"{name} missing @module: tag"
        assert "@flow:" in content, f"{name} missing @flow: tag"
        assert "@risk:" in content, f"{name} missing @risk: tag"


def test_payment_sandbox_template_uses_documented_test_card(
    tmp_path: Path,
    representative_graph: tuple[DiscoveryGraph, RiskMap, IdGenerator],
) -> None:
    """The payment template uses Stripe's published 4242 test card and gates
    the test on ``SENTINEL_PAYMENT_SANDBOX=1`` — never a real key.

    This is a safety-boundary check (CLAUDE §6, our product spec): the generator
    must never emit a spec that submits a production card number.
    """

    graph, risk, ids = representative_graph
    config = load_config(_write_config(tmp_path))
    plan = (
        DeterministicPlanner(id_generator=ids)
        .plan(graph, risk, config, run_id="RUN-PAYCAAAAAAAA")
        .plan
    )
    pipeline = GeneratorPipeline()
    result = pipeline.generate(
        GenerationInputs(
            plan=plan,
            graph=graph,
            out_dir=tmp_path / "tests",
            options=GenerationOptions(
                base_url="http://localhost:3000",
                security_mode="safe",
            ),
        )
    )
    payment_specs = [f for f in result.files_by_kind("spec") if "payment" in f.path.name.lower()]
    assert payment_specs, "expected at least one payment_sandbox spec"
    for spec in payment_specs:
        assert "4242 4242 4242 4242" in spec.content
        assert "SENTINEL_PAYMENT_SANDBOX" in spec.content
        # Production-card patterns must not appear.
        assert "5555 5555 5555 4444" not in spec.content


def test_login_spec_uses_env_var_credentials_not_inline(
    tmp_path: Path,
    representative_graph: tuple[DiscoveryGraph, RiskMap, IdGenerator],
) -> None:
    """Generated login specs must read credentials from env vars (CLAUDE §33)."""

    graph, risk, ids = representative_graph
    config = load_config(_write_config(tmp_path))
    plan = (
        DeterministicPlanner(id_generator=ids)
        .plan(graph, risk, config, run_id="RUN-LGNCAAAAAAAA")
        .plan
    )
    pipeline = GeneratorPipeline()
    result = pipeline.generate(
        GenerationInputs(
            plan=plan,
            graph=graph,
            out_dir=tmp_path / "tests",
            options=GenerationOptions(
                base_url="http://localhost:3000",
                security_mode="safe",
                username_env="SENTINEL_USERNAME",
                password_env="SENTINEL_PASSWORD",
            ),
        )
    )
    # Pick specs whose source flow is the dedicated login extractor (not the
    # route smoke spec that happens to share the path).
    login_specs = [
        f
        for f in result.files_by_kind("spec")
        if '@flow:login"' in f.content
        or "@flow:login " in f.content
        or "@flow:login\n" in f.content
    ]
    assert login_specs, "expected at least one login spec"
    for spec in login_specs:
        # process.env['SENTINEL_USERNAME'] is the canonical pattern.
        assert "SENTINEL_USERNAME" in spec.content
        assert "SENTINEL_PASSWORD" in spec.content
        # No inline credentials.
        assert "sentinel+password@example.com" not in spec.content
