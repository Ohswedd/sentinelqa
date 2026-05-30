"""Shared helpers for Phase 26 example-app integration tests.

These tests are structural — they assert the example apps exist, ship
their `sentinel.config.yaml`, expose the routes their READMEs claim,
and (where applicable) demonstrate the LLM-audit anti-patterns the
Phase 19 demo depends on. They do NOT boot Node.js / Docker; running
the demos themselves is documented in each example's README and the
top-level `make demo-*` targets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.config.loader import load_config
from engine.config.schema import RootConfig


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples"


def load_example_config(name: str) -> RootConfig:
    """Load and return the parsed `sentinel.config.yaml` for one example."""
    path = EXAMPLES / name / "sentinel.config.yaml"
    if not path.is_file():
        pytest.fail(f"missing example config: {path}")
    return load_config(path)


def read_text(name: str, *parts: str) -> str:
    """Return the contents of a checked-in example file."""
    path = EXAMPLES / name / Path(*parts)
    if not path.is_file():
        pytest.fail(f"missing example file: {path}")
    return path.read_text(encoding="utf-8")
