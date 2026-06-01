"""Structural smoke for the React + Vite example."""

from __future__ import annotations

import json

from .conftest import EXAMPLES, load_example_config, read_text


def test_vite_layout_present() -> None:
    root = EXAMPLES / "react-vite"
    for marker in (
        "package.json",
        "vite.config.ts",
        "tsconfig.json",
        "index.html",
        "README.md",
        "src/main.tsx",
        "src/App.tsx",
        "src/auth.tsx",
        "src/api.ts",
        "src/routes/Home.tsx",
        "src/routes/Login.tsx",
        "src/routes/Projects.tsx",
        "src/routes/NotFound.tsx",
    ):
        assert (root / marker).is_file(), marker


def test_vite_config_loads_and_uses_playwright_discovery() -> None:
    cfg = load_example_config("react-vite")
    assert cfg.project.framework == "react"
    assert cfg.discovery.engine == "playwright"
    assert str(cfg.target.base_url).startswith("http://127.0.0.1:5173")


def test_vite_package_pins_react_18_and_router_6() -> None:
    pkg = json.loads(read_text("react-vite", "package.json"))
    assert pkg["dependencies"]["react"].startswith("18.")
    assert pkg["dependencies"]["react-router-dom"].startswith("6.")
    assert pkg["devDependencies"]["vite"].startswith("5.")


def test_vite_app_routes_match_readme() -> None:
    main = read_text("react-vite", "src", "main.tsx")
    # README enumerates these routes; assert they all live in the router config.
    for path in ("path: \"login\"", "path: \"projects\"", "path: \"*\""):
        assert path in main, path
