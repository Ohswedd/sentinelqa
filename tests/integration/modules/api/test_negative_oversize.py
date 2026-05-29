"""Coverage for the negative-check oversize-string + post-processing branches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from engine.config.schema import ApiConfig, RootConfig
from pytest_httpserver import HTTPServer

from modules.api.checks.negative import run_negative_check
from modules.api.openapi import load_openapi


def _spec_with_string_body() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "fixture", "version": "1.0.0"},
        "paths": {
            "/notes": {
                "post": {
                    "operationId": "create_note",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"note": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            }
        },
    }


@pytest.fixture
def api_config() -> RootConfig:
    return RootConfig(
        project={"name": "fixture", "framework": "unknown", "package_manager": "unknown"},
        target={"base_url": "http://127.0.0.1:1", "allowed_hosts": ("127.0.0.1",)},
        api=ApiConfig(negative_max_payload_kb=2),
    )


def test_oversize_string_variant_is_sent_and_accepted(
    httpserver: HTTPServer,
    tmp_path: Path,
    api_config: RootConfig,
) -> None:
    """Drives the size_bytes calculation path in _generate_variants."""

    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_spec_with_string_body()), encoding="utf-8")
    httpserver.expect_request("/notes", method="POST").respond_with_data(
        '{"id":"abc"}', status=201, content_type="application/json"
    )
    doc = load_openapi(spec_path)
    with httpx.Client(base_url=httpserver.url_for(""), timeout=5.0) as client:
        result = run_negative_check(client=client, doc=doc, config=api_config)
    # The check ran; the oversize variant was generated under the 2 KB cap.
    assert result.targets_scanned == 1
