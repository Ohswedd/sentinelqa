"""Per-extractor unit tests (task 06.02)."""

from __future__ import annotations

import pytest
from engine.domain.discovery_graph import AuthBoundary, DiscoveryGraph
from engine.domain.form import Form, FormField
from engine.domain.ids import IdGenerator
from engine.domain.route import Route
from engine.planner.flows import (
    PROPOSAL_THRESHOLD,
    AdminFlowExtractor,
    CrudFlowExtractor,
    FileUploadDownloadFlowExtractor,
    LoginFlowExtractor,
    LogoutFlowExtractor,
    NotificationFlowExtractor,
    PasswordResetFlowExtractor,
    PaymentSandboxFlowExtractor,
    RoleFlowExtractor,
    SearchFilterSortFlowExtractor,
    SignupFlowExtractor,
    builtin_extractors,
    run_extractors,
)


def _graph(
    ids: IdGenerator, *, routes=(), forms=(), api_endpoints=(), boundaries=()
) -> DiscoveryGraph:
    return DiscoveryGraph(
        id=ids.new("DG"),
        routes=tuple(routes),
        forms=tuple(forms),
        api_endpoints=tuple(api_endpoints),
        auth_boundaries=tuple(boundaries),
    )


# ----------------------------------------------------------------------
# Login extractor
# ----------------------------------------------------------------------


def test_login_extractor_finds_form_with_email_password(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/login")
    form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/login",
        method="POST",
        fields=(
            FormField(name="email", type="email", required=True),
            FormField(name="password", type="password", required=True),
        ),
    )
    out = LoginFlowExtractor().extract(_graph(ids, routes=[rt], forms=[form]), id_generator=ids)
    assert len(out) == 1
    flow = out[0]
    assert flow.name == "login"
    assert flow.priority == "P0"
    assert flow.risk == "critical"
    assert "auth" in flow.tags


def test_login_extractor_route_only_low_confidence(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/login")
    out = LoginFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1
    flow = out[0]
    assert flow.confidence < PROPOSAL_THRESHOLD
    assert "confidence_low" in flow.tags


def test_login_extractor_no_match_emits_nothing(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/dashboard")
    out = LoginFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert out == ()


# ----------------------------------------------------------------------
# Signup
# ----------------------------------------------------------------------


def test_signup_extractor_matches_paths(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/sign-up")
    out = SignupFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1
    assert out[0].priority == "P0"


# ----------------------------------------------------------------------
# Logout
# ----------------------------------------------------------------------


def test_logout_extractor_matches(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/logout")
    out = LogoutFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1
    assert out[0].name == "logout"


# ----------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------


def test_password_reset_extractor_matches(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/forgot-password")
    out = PasswordResetFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1
    assert out[0].name == "password reset"


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------


def test_crud_extractor_emits_four_flows_per_collection(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    list_route = Route(id=ids.new("RT"), path="/api/items")
    detail = Route(id=ids.new("RT"), path="/api/items/[id]")
    out = CrudFlowExtractor().extract(_graph(ids, routes=[list_route, detail]), id_generator=ids)
    names = sorted(f.name for f in out)
    assert names == [
        "crud:create /api/items",
        "crud:delete /api/items",
        "crud:read /api/items",
        "crud:update /api/items",
    ]


def test_crud_extractor_no_templates_emits_nothing(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/about")
    out = CrudFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert out == ()


# ----------------------------------------------------------------------
# Search/filter/sort
# ----------------------------------------------------------------------


def test_search_filter_sort_extractor_matches(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/search")
    out = SearchFilterSortFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1


# ----------------------------------------------------------------------
# Admin
# ----------------------------------------------------------------------


def test_admin_extractor_matches_and_uses_boundary_role(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/admin/users", auth_required=True)
    boundary = AuthBoundary(route_id=rt.id, required_role="superuser")
    out = AdminFlowExtractor().extract(
        _graph(ids, routes=[rt], boundaries=[boundary]), id_generator=ids
    )
    assert len(out) == 1
    assert out[0].required_auth_role == "superuser"


# ----------------------------------------------------------------------
# Role
# ----------------------------------------------------------------------


def test_role_extractor_uses_named_boundary(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/reports", auth_required=True)
    boundary = AuthBoundary(route_id=rt.id, required_role="manager")
    out = RoleFlowExtractor().extract(
        _graph(ids, routes=[rt], boundaries=[boundary]), id_generator=ids
    )
    assert len(out) == 1
    assert out[0].required_auth_role == "manager"


def test_role_extractor_skips_anonymous_boundaries(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/x", auth_required=True)
    boundary = AuthBoundary(route_id=rt.id, required_role=None)
    out = RoleFlowExtractor().extract(
        _graph(ids, routes=[rt], boundaries=[boundary]), id_generator=ids
    )
    assert out == ()


# ----------------------------------------------------------------------
# File upload / download
# ----------------------------------------------------------------------


def test_file_upload_extractor_finds_file_forms(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/upload")
    form = Form(
        id=ids.new("FRM"),
        action_url="http://localhost:3000/upload",
        method="POST",
        fields=(FormField(name="document", type="file", required=True),),
    )
    out = FileUploadDownloadFlowExtractor().extract(
        _graph(ids, routes=[rt], forms=[form]), id_generator=ids
    )
    assert any(f.name == "file upload" for f in out)


def test_file_download_extractor_finds_download_routes(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/files/download")
    out = FileUploadDownloadFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert any("file download" in f.name for f in out)


# ----------------------------------------------------------------------
# Payment sandbox
# ----------------------------------------------------------------------


def test_payment_sandbox_extractor_matches_and_tags_provider(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/checkout/stripe")
    out = PaymentSandboxFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1
    assert any("provider:stripe" in tag for tag in out[0].tags)


def test_payment_sandbox_never_uses_production(deterministic_ids: IdGenerator) -> None:
    """Safety boundary: no flow may mention production credentials."""

    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/billing")
    out = PaymentSandboxFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    for flow in out:
        assert "production" not in flow.description.lower() or "never" in flow.description.lower()
        for step in flow.steps:
            assert "production" not in step.description.lower()


# ----------------------------------------------------------------------
# Notification callback
# ----------------------------------------------------------------------


def test_notification_extractor_matches_token_routes(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/verify/[token]")
    out = NotificationFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    assert len(out) == 1


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------


@pytest.mark.parametrize("extractor", builtin_extractors())
def test_every_extractor_has_a_name(extractor) -> None:
    assert isinstance(extractor.name, str) and extractor.name


def test_run_extractors_concatenates(deterministic_ids: IdGenerator) -> None:
    ids = deterministic_ids
    login = Route(id=ids.new("RT"), path="/login")
    signup = Route(id=ids.new("RT"), path="/signup")
    out = run_extractors(
        builtin_extractors(), _graph(ids, routes=[login, signup]), id_generator=ids
    )
    names = {f.extractor for f in out}
    assert "login" in names
    assert "signup" in names


def test_low_confidence_flows_carry_confidence_low_tag(
    deterministic_ids: IdGenerator,
) -> None:
    ids = deterministic_ids
    rt = Route(id=ids.new("RT"), path="/login")
    out = LoginFlowExtractor().extract(_graph(ids, routes=[rt]), id_generator=ids)
    for flow in out:
        if flow.confidence < PROPOSAL_THRESHOLD:
            assert "confidence_low" in flow.tags
