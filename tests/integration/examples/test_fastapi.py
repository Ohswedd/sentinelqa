"""Structural smoke for the FastAPI example (Phase 26.02)."""

from __future__ import annotations

import json

from .conftest import EXAMPLES, load_example_config, read_text


def test_fastapi_layout_present() -> None:
    root = EXAMPLES / "fastapi"
    assert (root / "app" / "main.py").is_file()
    assert (root / "app" / "__init__.py").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "README.md").is_file()
    assert (root / "openapi.json").is_file()


def test_fastapi_config_loads_with_api_module() -> None:
    cfg = load_example_config("fastapi")
    assert cfg.project.name == "sentinelqa-fastapi-example"
    assert cfg.project.framework == "fastapi"
    assert str(cfg.target.base_url).startswith("http://127.0.0.1:8000")
    assert cfg.modules.api is True
    assert str(cfg.api.openapi_path) == "openapi.json"


def test_fastapi_openapi_is_valid_3x() -> None:
    raw = (EXAMPLES / "fastapi" / "openapi.json").read_text(encoding="utf-8")
    spec = json.loads(raw)
    assert spec["openapi"].startswith("3."), spec["openapi"]
    paths = set(spec["paths"].keys())
    # /projects and /projects/{project_id} ship for full CRUD; /health is a
    # liveness probe.
    assert "/health" in paths
    assert "/projects" in paths
    assert "/projects/{project_id}" in paths


def test_fastapi_app_implements_full_crud() -> None:
    src = read_text("fastapi", "app", "main.py")
    for marker in (
        '@app.get("/health"',
        '@app.get("/projects"',
        '@app.post(\n    "/projects"',
        '@app.get("/projects/{project_id}"',
        '@app.put("/projects/{project_id}"',
        '@app.delete(\n    "/projects/{project_id}"',
    ):
        assert marker in src, marker
