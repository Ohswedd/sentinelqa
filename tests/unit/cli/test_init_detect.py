"""Framework / package-manager detection helpers (task 02.02)."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel_cli import init_detect


def test_nextjs_detected_via_config(tmp_path: Path) -> None:
    (tmp_path / "next.config.js").write_text("// config", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "nextjs"


def test_vite_maps_to_react(tmp_path: Path) -> None:
    (tmp_path / "vite.config.ts").write_text("// config", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "react"


def test_package_json_dep_detected(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"@angular/core": "17"}}),
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "angular"


def test_fastapi_via_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["fastapi==0.111"]\n',
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "fastapi"


def test_django_via_requirements(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("Django==5.0\n", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "django"


def test_package_manager_detection(tmp_path: Path) -> None:
    assert init_detect.detect_package_manager(tmp_path) == "unknown"
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    assert init_detect.detect_package_manager(tmp_path) == "pnpm"


def test_playwright_dep(tmp_path: Path) -> None:
    assert init_detect.detect_playwright(tmp_path) is False
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"@playwright/test": "^1.49"}}),
        encoding="utf-8",
    )
    assert init_detect.detect_playwright(tmp_path) is True


def test_detection_combined(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"react": "18"}}),
        encoding="utf-8",
    )
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    detection = init_detect.detect(tmp_path)
    assert detection.framework == "react"
    assert detection.package_manager == "yarn"
    assert detection.project_name == "demo"


def test_corrupt_package_json_handled(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not json", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "unknown"
    assert init_detect.detect_project_name(tmp_path)  # falls back to dir name


def test_express_detection(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"express": "5"}}),
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "express"


def test_svelte_and_vue_detection(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"svelte": "5"}}),
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "svelte"
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"vue": "3"}}),
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "vue"


def test_flask_via_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies = ["flask"]\n',
        encoding="utf-8",
    )
    assert init_detect.detect_framework(tmp_path) == "flask"


def test_fastapi_via_requirements(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("fastapi==0.115\n", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "fastapi"


def test_flask_via_requirements(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("flask==3\n", encoding="utf-8")
    assert init_detect.detect_framework(tmp_path) == "flask"


def test_npm_lockfile(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    assert init_detect.detect_package_manager(tmp_path) == "npm"


def test_uv_lockfile(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    assert init_detect.detect_package_manager(tmp_path) == "uv"


def test_pip_via_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert init_detect.detect_package_manager(tmp_path) == "pip"


def test_pyproject_project_name(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "from-pyproject"\n',
        encoding="utf-8",
    )
    assert init_detect.detect_project_name(tmp_path) == "from-pyproject"


def test_render_config_compiles(tmp_path: Path) -> None:
    from engine.config.loader import dump_config

    detection = init_detect.Detection(
        framework="nextjs",
        package_manager="pnpm",
        has_playwright=True,
        project_name="alpha",
        base_url=None,
    )
    yaml_body = init_detect.render_config(
        project_root=tmp_path,
        detection=detection,
        dump_config=dump_config,
    )
    assert "alpha" in yaml_body
    assert "nextjs" in yaml_body
    assert "pnpm" in yaml_body


def test_read_text_safe_handles_too_big(tmp_path: Path, monkeypatch) -> None:
    big = tmp_path / "package.json"
    big.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(init_detect, "_MAX_READ_BYTES", 10)
    assert init_detect._read_text_safe(big) is None


def test_read_text_safe_missing(tmp_path: Path) -> None:
    assert init_detect._read_text_safe(tmp_path / "nope.txt") is None
