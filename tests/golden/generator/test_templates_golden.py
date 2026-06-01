"""Golden test for rendered templates.

Locks the byte-output of every template against a fixed context. Run
``SENTINELQA_UPDATE_GOLDENS=1 pytest tests/golden/generator`` to
regenerate after deliberate template changes; the diff is the review.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from engine.generator.render import render_template

GOLDEN_DIR: Path = Path(__file__).parent / "fixtures"


def _update_mode() -> bool:
    return os.environ.get("SENTINELQA_UPDATE_GOLDENS") == "1"


def _assert_golden(name: str, rendered: str) -> None:
    target = GOLDEN_DIR / name
    if _update_mode():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        return
    if not target.exists():  # pragma: no cover - golden bootstrapping branch
        pytest.fail(
            f"golden file {target} missing; run "
            "`SENTINELQA_UPDATE_GOLDENS=1 pytest tests/golden/generator` to create it."
        )
    expected = target.read_text(encoding="utf-8")
    if expected != rendered:  # pragma: no cover - failure-only diff
        pytest.fail(
            f"golden mismatch for {name}:\n--- expected\n{expected}\n--- actual\n{rendered}"
        )


CASES = {
    "smoke.spec.ts": (
        "smoke.spec.ts.j2",
        {
            "describe_title": "Smoke /login",
            "test_title": "smoke /login",
            "tags": ["@p0", "@critical"],
            "route_path": "/login",
            "anchor_role": "heading",
            "anchor_name": "sign in",
        },
    ),
    "smoke_no_anchor.spec.ts": (
        "smoke.spec.ts.j2",
        {
            "describe_title": "Smoke /",
            "test_title": "smoke /",
            "tags": ["@p3"],
            "route_path": "/",
            "anchor_role": "",
            "anchor_name": "",
        },
    ),
    "login.spec.ts": (
        "login.spec.ts.j2",
        {
            "tags": ["@p0", "@auth"],
            "login_path": "/login",
            "email_env_name": "SENTINEL_EMAIL",
            "password_env_name": "SENTINEL_PASSWORD",
            "email_label": "email",
            "password_label": "password",
            "submit_label": "sign in|log in",
            "success_url_regex": "dashboard|home",
            "validation_message_regex": "required|invalid",
            "post_login_role": "navigation",
        },
    ),
    "signup.spec.ts": (
        "signup.spec.ts.j2",
        {
            "tags": ["@p0"],
            "signup_path": "/signup",
            "sample_email": "sentinel+signup@example.com",
            "sample_password": "S3ntinel-Sample!",
            "email_label": "email",
            "password_label": "password",
            "confirm_password_label": "confirm password",
            "submit_label": "create account|sign up",
            "success_url_regex": "welcome|onboarding",
            "invalid_email_regex": "valid email",
        },
    ),
    "logout.spec.ts": (
        "logout.spec.ts.j2",
        {
            "tags": ["@p1"],
            "start_path": "/dashboard",
            "logout_label": "log out|sign out",
            "post_logout_url_regex": "login|home",
            "post_logout_text": "logged out",
        },
    ),
    "crud_create.spec.ts": (
        "crud_create.spec.ts.j2",
        {
            "tags": ["@p1"],
            "resource_title": "Records",
            "resource_singular": "record",
            "create_path": "/records/new",
            "fields": [{"label": "name", "sample_value": "Sentinel sample"}],
            "submit_label": "create|save",
            "success_url_regex": "records",
            "success_text": "created",
            "required_error_regex": "required",
        },
    ),
    "crud_read.spec.ts": (
        "crud_read.spec.ts.j2",
        {
            "tags": ["@p2"],
            "resource_title": "Records",
            "resource_plural": "records",
            "resource_singular": "record",
            "list_path": "/records",
            "list_role": "list",
            "list_name": "records",
            "detail_path": "/records/123",
        },
    ),
    "crud_update.spec.ts": (
        "crud_update.spec.ts.j2",
        {
            "tags": ["@p1"],
            "resource_title": "Records",
            "resource_singular": "record",
            "edit_path": "/records/123/edit",
            "field_label": "name",
            "updated_value": "updated",
            "save_label": "save|update",
            "success_url_regex": "records",
            "success_text": "saved",
        },
    ),
    "crud_delete.spec.ts": (
        "crud_delete.spec.ts.j2",
        {
            "tags": ["@p1"],
            "resource_title": "Records",
            "resource_singular": "record",
            "detail_path": "/records/123",
            "delete_label": "delete|remove",
            "confirm_dialog_label": "confirm|yes",
            "post_delete_url_regex": "records",
            "success_text": "deleted",
        },
    ),
    "role_boundary.spec.ts": (
        "role_boundary.spec.ts.j2",
        {
            "tags": ["@p0", "@security"],
            "describe_title": "Admin /admin",
            "protected_path": "/admin",
            "required_role": "admin",
        },
    ),
    "payment_sandbox.spec.ts": (
        "payment_sandbox.spec.ts.j2",
        {
            "tags": ["@p0", "@payment"],
            "checkout_path": "/checkout",
            "sandbox_card_number": "4242 4242 4242 4242",
            "sandbox_card_exp": "12 / 34",
            "sandbox_card_cvc": "123",
            "card_number_label": "card number",
            "card_exp_label": "expiration",
            "card_cvc_label": "cvc",
            "pay_label": "pay|complete order",
            "success_text": "thank you",
        },
    ),
    "file_upload.spec.ts": (
        "file_upload.spec.ts.j2",
        {
            "tags": ["@p2"],
            "upload_path": "/upload",
            "fixture_kind": "text",
            "fixture_file_name": "sentinel-fixture.txt",
            "fixture_mime_type": "text/plain",
            "fixture_base64": "U2VudGluZWxRQQ==",
            "upload_label": "upload",
            "submit_label": "upload",
            "success_text": "uploaded",
        },
    ),
    "api_contract.spec.ts": (
        "api_contract.spec.ts.j2",
        {
            "tags": ["@p1", "@api"],
            "endpoint_title": "GET /api/users",
            "method": "GET",
            "path": "/api/users",
            "request_path": "/api/users",
            "request_body_json": "",
            "expected_status": [200],
            "expected_content_type": "json",
            "skip_unauth_test": True,
        },
    ),
    "a11y_axe.spec.ts": (
        "a11y_axe.spec.ts.j2",
        {
            "tags": ["@p2", "@a11y"],
            "route_title": "Smoke /",
            "route_path": "/",
        },
    ),
    "perf_budget.spec.ts": (
        "perf_budget.spec.ts.j2",
        {
            "tags": ["@p2", "@perf"],
            "route_title": "Home",
            "route_path": "/",
            "load_budget_ms": 3000,
            "bytes_budget": 1500000,
        },
    ),
}


@pytest.mark.parametrize("name", sorted(CASES.keys()))
def test_template_golden(name: str) -> None:
    template, ctx = CASES[name]
    rendered = render_template(template, ctx)
    _assert_golden(name, rendered)
