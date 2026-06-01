"""Structural smoke for the end-to-end demo (Phase 26.07).

The acceptance criterion ("compose up, audit, score >= threshold") is
exercised manually via `make demo` — both Docker and the example apps'
own dependencies have to be available. Here we assert the compose file
is internally consistent and that the README documents the agreed
contract so doc / Make / compose drift fails CI.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .conftest import EXAMPLES, read_text

DEMO = EXAMPLES / "end-to-end-demo"
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_end_to_end_layout_present() -> None:
    assert (DEMO / "docker-compose.yml").is_file()
    assert (DEMO / "README.md").is_file()


def test_compose_file_ties_examples_together_on_loopback() -> None:
    compose = yaml.safe_load((DEMO / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"fastapi", "nextjs"}
    # Both services bind to 127.0.0.1 only — CLAUDE §6 / our product spec safety boundary.
    assert services["fastapi"]["ports"] == ["127.0.0.1:8000:8000"]
    assert services["nextjs"]["ports"] == ["127.0.0.1:3000:3000"]
    # The Next.js service must wait on the FastAPI backend.
    assert services["nextjs"]["depends_on"] == ["fastapi"]
    # Volume mounts point at the existing example dirs rather than duplicating.
    assert services["fastapi"]["volumes"] == ["../fastapi:/app:ro"]
    assert services["nextjs"]["volumes"] == ["../nextjs:/app"]


def test_makefile_exposes_demo_lifecycle() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    # `make demo` orchestrates compose up + sentinel audit; `make demo-down`
    # tears it down.
    assert "\ndemo:\n" in makefile
    assert "\ndemo-down:\n" in makefile
    assert "docker compose up" in makefile
    assert "sentinel audit" in makefile


def test_demo_readme_documents_make_targets() -> None:
    readme = read_text("end-to-end-demo", "README.md")
    assert "make demo" in readme
    assert "make demo-down" in readme
    assert "under 10 minutes" in readme  # Phase 26.07 acceptance copy
